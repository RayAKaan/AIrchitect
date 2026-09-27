"""Content-addressed storage for CAD artifacts.

Geometry leaves the worker as base64 in a JSON response. This module turns that
into bytes on disk and hands back the metadata the database needs -- size, hash,
and a ``storage_key`` -- without ever putting the payload in PostgreSQL. The
reason is scale and repetition: a single STEP file for a real project is tens of
megabytes, and the same geometry is regenerated on every run. Row-sized payloads
would bloat every table that references them, and backups would carry them.

The store is content-addressed. The file name is derived from the SHA-256 of the
bytes, so identical geometry from two different runs resolves to one file and a
later run can never silently change what an earlier database row points at. It is
also why ``put_bytes`` is safe to call twice: the second call is a no-op if the
object is already present.

Writes are atomic. Bytes go to a temporary file in the destination directory and
are then renamed into place, so a reader can never observe a half-written GLB
that a crashed run left behind. Rename is atomic within a filesystem on both NTFS
and POSIX, which is why the temporary file is created in the destination
directory rather than in a system temp folder.

Nothing from a caller reaches the filesystem. The extension comes from the
protocol's fixed kind mapping, and ``resolve`` refuses any key that escapes the
root, so a malicious or corrupted ``storage_key`` cannot turn a download into a
file read.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.domains.cad.errors import CadArtifactMissingError, CadStorageError
from app.domains.cad.protocol import ARTIFACT_EXTENSIONS

#: What each artifact is for, so a consumer selects the viewer mesh by role instead
#: of hard-coding a file extension. This is API policy rather than a fact about the
#: bytes, which is why it lives here and not in the protocol: the worker has no
#: opinion about who will read the file.
ARTIFACT_MEDIA_ROLES: dict[str, str] = {
    "glb": "viewer_primary",
    "ifc": "exchange",
    "step": "exchange",
    "brep": "intermediate",
    "freecad_document": "intermediate",
}

#: Path segments are restricted to a conservative token set. Every value that lands
#: in a key is generated here, but validating anyway means a future caller cannot
#: smuggle a separator or a Windows reserved name into the layout by accident.
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_HASH_CHUNK = 1024 * 1024


@dataclass(frozen=True, slots=True)
class StoredBlob:
    """A blob now on disk, with everything the ``cad_artifacts`` row needs.

    ``content_type`` is passed in rather than derived. The worker computes it from
    the artifact it actually produced and reports it in the result; deriving it here
    would mean a second table to keep in step with the worker's, and the two already
    disagreed once. Deriving it is a naming decision; reporting it is a fact about
    the bytes, and only the producer knows which is which.
    """

    kind: str
    filename: str
    content_type: str | None
    byte_size: int
    sha256: str
    storage_key: str
    path: Path
    media_role: str
    deduplicated: bool


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


class ContentAddressedStore:
    """Stores CAD artifacts under a root directory, addressed by content hash.

    Layout::

        <root>/cad/<organization>/<hh>/<sha256><extension>

    The organisation segment keeps tenants physically separated, so an accidental
    cross-tenant read fails at the filesystem boundary as well as in the query that
    was supposed to prevent it. The two-character shard directory keeps any single
    directory from growing unbounded as the artifact count grows.
    """

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _key_for(self, organization_id: str, sha256: str, kind: str) -> str:
        if not _SAFE_SEGMENT.match(organization_id):
            raise CadStorageError(f"unsafe organization segment: {organization_id!r}")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise CadStorageError(f"malformed content hash: {sha256!r}")
        extension = ARTIFACT_EXTENSIONS.get(kind)
        if extension is None:
            raise CadStorageError(f"unknown artifact kind: {kind!r}")
        return str(PurePosixPath("cad") / organization_id / sha256[:2] / f"{sha256}{extension}")

    def resolve(self, storage_key: str) -> Path:
        """Turn a ``storage_key`` into an absolute path inside the root.

        Raises rather than clamping: a key that escapes the root is a bug or an
        attack, and silently rewriting it would hide both. Backslashes are rejected
        as well as ``..`` because a key produced on POSIX is read on Windows.
        """
        if not storage_key or storage_key.startswith("/") or "\\" in storage_key:
            raise CadStorageError(f"malformed storage key: {storage_key!r}")
        candidate = PurePosixPath(storage_key)
        if any(segment in {"..", ""} for segment in candidate.parts):
            raise CadStorageError(f"storage key escapes the artifact root: {storage_key!r}")
        resolved = (self.root / candidate).resolve()
        # Belt and braces: even with the checks above, confirm containment. The
        # comparison is case-insensitive because the root may be on NTFS, where
        # "C:\Cad" and "c:\cad" are the same directory.
        if os.path.normcase(str(resolved)) != os.path.normcase(str(self.root)) and not str(
            resolved
        ).lower().startswith(str(self.root).lower() + os.sep.lower()):
            raise CadStorageError(f"storage key escapes the artifact root: {storage_key!r}")
        return resolved

    def put_bytes(
        self,
        data: bytes,
        *,
        organization_id: str,
        kind: str,
        content_type: str | None = None,
    ) -> StoredBlob:
        """Store ``data`` and return its metadata.

        Idempotent: if the object is already present the existing file is kept and
        the result is flagged as a deduplication hit. The content hash is computed
        from the bytes, so the name is verified rather than trusted.
        """
        extension = ARTIFACT_EXTENSIONS.get(kind)
        if extension is None:
            raise CadStorageError(f"unknown artifact kind: {kind!r}")
        digest = sha256_bytes(data)
        key = self._key_for(organization_id, digest, kind)
        destination = self.resolve(key)
        if destination.exists():
            return self._describe(
                kind, digest, key, destination, content_type=content_type, deduplicated=True
            )

        destination.parent.mkdir(parents=True, exist_ok=True)
        # Same directory as the destination so os.replace stays within one
        # filesystem and therefore stays atomic.
        handle, temporary_name = tempfile.mkstemp(
            dir=destination.parent, prefix=".partial-", suffix=extension
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        except BaseException:
            # A failed run must not leave a partial file that a later reader would
            # treat as a valid artifact.
            temporary.unlink(missing_ok=True)
            raise
        return self._describe(
            kind, digest, key, destination, content_type=content_type, deduplicated=False
        )

    def _describe(
        self,
        kind: str,
        digest: str,
        key: str,
        path: Path,
        *,
        content_type: str | None,
        deduplicated: bool,
    ) -> StoredBlob:
        return StoredBlob(
            kind=kind,
            filename=path.name,
            content_type=content_type,
            byte_size=path.stat().st_size,
            sha256=digest,
            storage_key=key,
            path=path,
            media_role=ARTIFACT_MEDIA_ROLES[kind],
            deduplicated=deduplicated,
        )

    def exists(self, storage_key: str) -> bool:
        return self.resolve(storage_key).is_file()

    def read_bytes(self, storage_key: str) -> bytes:
        path = self.resolve(storage_key)
        if not path.is_file():
            raise CadArtifactMissingError(f"artifact not found: {storage_key}")
        data = path.read_bytes()
        # Cheap insurance against a truncated or externally modified object: the
        # key is the hash, so a mismatch means the store is no longer trustworthy.
        actual = sha256_bytes(data)
        expected = PurePosixPath(storage_key).name.split(".")[0]
        if actual != expected:
            raise CadStorageError(
                f"artifact content does not match its key (expected {expected}, got {actual})"
            )
        return data

    def delete(self, storage_key: str) -> None:
        self.resolve(storage_key).unlink(missing_ok=True)

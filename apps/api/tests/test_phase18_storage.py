"""Tests for content-addressed CAD artifact storage.

The properties under test are the ones the persistence layer relies on and cannot
recover from on its own: the payload never lands in the database, the key always
matches the content, and a hostile key cannot read outside the root.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.domains.cad.errors import CadStorageError
from app.domains.cad.protocol import ALLOWED_ARTIFACT_SUFFIXES, ARTIFACT_CONTENT_TYPES
from app.domains.cad.storage import (
    ARTIFACT_MEDIA_ROLES,
    CadArtifactMissingError,
    ContentAddressedStore,
    sha256_bytes,
)

ORG = "11111111-1111-1111-1111-111111111111"

# A small but structurally valid GLB header: magic "glTF" + version 2.
GLB = b"glTF" + (2).to_bytes(4, "little") + (12).to_bytes(4, "little") + b"\x00" * 8


def test_put_bytes_returns_row_ready_metadata(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    blob = store.put_bytes(
        GLB, organization_id=ORG, kind="glb", content_type=ARTIFACT_CONTENT_TYPES["glb"]
    )

    assert blob.kind == "glb"
    assert blob.byte_size == len(GLB)
    assert blob.sha256 == sha256_bytes(GLB)
    # the content type is carried through from the producer, not derived here
    assert blob.content_type == ARTIFACT_CONTENT_TYPES["glb"]
    assert blob.media_role == ARTIFACT_MEDIA_ROLES["glb"] == "viewer_primary"
    assert blob.path.is_file()
    assert blob.path.read_bytes() == GLB


def test_content_type_is_optional(tmp_path: Path) -> None:
    """The store does not invent a content type; it records what it was given."""
    store = ContentAddressedStore(tmp_path)
    blob = store.put_bytes(GLB, organization_id=ORG, kind="glb")
    assert blob.content_type is None


def test_key_is_content_addressed_and_sharded(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    blob = store.put_bytes(GLB, organization_id=ORG, kind="glb")
    digest = sha256_bytes(GLB)

    # name is the content hash; the shard is the first two hex digits of it
    assert blob.storage_key == f"cad/{ORG}/{digest[:2]}/{digest}.glb"
    assert blob.path.parent.name == digest[:2]


def test_identical_content_deduplicates_to_one_file(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    first = store.put_bytes(GLB, organization_id=ORG, kind="glb")
    second = store.put_bytes(GLB, organization_id=ORG, kind="glb")

    assert first.storage_key == second.storage_key
    assert first.deduplicated is False
    assert second.deduplicated is True
    files = [p for p in (tmp_path / "cad" / ORG).rglob("*") if p.is_file()]
    assert len(files) == 1


def test_tenants_never_share_a_file(tmp_path: Path) -> None:
    """Same geometry, different orgs: two objects, so no cross-tenant bleed."""
    other = "22222222-2222-2222-2222-222222222222"
    store = ContentAddressedStore(tmp_path)
    a = store.put_bytes(GLB, organization_id=ORG, kind="glb")
    b = store.put_bytes(GLB, organization_id=other, kind="glb")

    assert a.storage_key != b.storage_key
    assert a.path != b.path
    assert a.sha256 == b.sha256  # same content, different address


def test_every_protocol_kind_can_be_stored(tmp_path: Path) -> None:
    """The store must cover exactly the protocol's artifact kinds, no more."""
    store = ContentAddressedStore(tmp_path)
    for kind in ARTIFACT_CONTENT_TYPES:
        blob = store.put_bytes(b"payload", organization_id=ORG, kind=kind)
        assert blob.path.suffix.lower() in ALLOWED_ARTIFACT_SUFFIXES
        assert blob.kind in ARTIFACT_MEDIA_ROLES
    assert set(ARTIFACT_CONTENT_TYPES) == set(ARTIFACT_MEDIA_ROLES.keys())


def test_unknown_kind_is_refused(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    for bad in ("exe", "py", "", "glb/../../etc/passwd"):
        with pytest.raises(CadStorageError):
            store.put_bytes(GLB, organization_id=ORG, kind=bad)


@pytest.mark.parametrize(
    "key",
    [
        "../outside.glb",
        "cad/../../outside.glb",
        "/etc/passwd",
        "cad\\..\\..\\outside.glb",
        "..",
        "",
    ],
)
def test_traversal_keys_are_refused(tmp_path: Path, key: str) -> None:
    store = ContentAddressedStore(tmp_path)
    with pytest.raises(CadStorageError):
        store.resolve(key)


def test_resolve_stays_inside_the_root(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    blob = store.put_bytes(GLB, organization_id=ORG, kind="glb")
    resolved = store.resolve(blob.storage_key)

    assert os.path.normcase(str(resolved)).startswith(os.path.normcase(str(store.root)) + os.sep.lower())


def test_unsafe_organization_segment_is_refused(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    for bad in ("../evil", "a/b", "a\\b", "", "x" * 65):
        with pytest.raises(CadStorageError):
            store.put_bytes(GLB, organization_id=bad, kind="glb")


def test_write_is_atomic_and_leaves_no_partial_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A crash mid-write must not leave a readable artifact behind."""
    store = ContentAddressedStore(tmp_path)
    real_replace = os.replace

    def explode(src: object, dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", explode)
    with pytest.raises(OSError):
        store.put_bytes(GLB, organization_id=ORG, kind="glb")
    monkeypatch.setattr(os, "replace", real_replace)

    shard = tmp_path / "cad" / ORG / sha256_bytes(GLB)[:2]
    assert list(shard.glob("*")) == [], "partial file was not cleaned up"
    assert not store.exists(f"cad/{ORG}/{sha256_bytes(GLB)[:2]}/{sha256_bytes(GLB)}.glb")


def test_read_round_trips_and_verifies_the_hash(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    blob = store.put_bytes(GLB, organization_id=ORG, kind="glb")
    assert store.read_bytes(blob.storage_key) == GLB
    assert store.exists(blob.storage_key) is True


def test_read_detects_content_that_no_longer_matches_its_key(tmp_path: Path) -> None:
    """An externally corrupted object is a failure, not a silent wrong answer."""
    store = ContentAddressedStore(tmp_path)
    blob = store.put_bytes(GLB, organization_id=ORG, kind="glb")
    blob.path.write_bytes(b"corrupted")

    with pytest.raises(CadStorageError):
        store.read_bytes(blob.storage_key)


def test_missing_object_raises_the_dedicated_error(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    digest = "a" * 64
    with pytest.raises(CadArtifactMissingError):
        store.read_bytes(f"cad/{ORG}/aa/{digest}.glb")


def test_empty_artifact_is_storable_and_readable(tmp_path: Path) -> None:
    """Zero bytes is unusual but must not break the hash-verified read path."""
    store = ContentAddressedStore(tmp_path)
    blob = store.put_bytes(b"", organization_id=ORG, kind="brep")
    assert blob.byte_size == 0
    assert store.read_bytes(blob.storage_key) == b""

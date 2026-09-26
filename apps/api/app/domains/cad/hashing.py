"""Semantic hashing for generated geometry.

The hash AIrchitect records against every geometry artifact must satisfy three
properties that a naive ``json.dumps`` hash does not:

1. **Volatile-field immunity.** Generation timestamps, temporary directory
   paths, database identifiers, and FreeCAD document GUIDs change on every single
   run. Including them would make every artifact unique and defeat the purpose of
   content addressing, so they are stripped before hashing.

2. **Numeric stability across toolchain versions.** Two different builds of OCCT
   can disagree in the last floating-point bit of a computed volume. Hashing raw
   floats would make FreeCAD 1.1.3 (OCCT 7.8.1) and a Docker worker (OCCT 7.9.3)
   hash differently for geometrically identical buildings. Values are therefore
   quantized to a fixed decimal precision chosen to be far coarser than kernel
   noise but far finer than any meaningful design change: 1 micrometre for
   lengths, 1e-9 for ratios, 1e-6 degrees for angles.

3. **Order independence where order is not meaningful.** Collections listed in
   :data:`UNORDERED_KEYS` (elements, masses, parts, ...) are sorted by their
   canonical form before hashing, so regenerating the same design with its parts
   discovered in a different order still yields the same hash. Order-*sensitive*
   lists, such as a footprint's ``points``, are deliberately left alone: their
   order is part of the geometry.

The hash is used to prove that a regenerated artifact is the *same* artifact.
It is deliberately not a security primitive; it is never used for authentication
or as a secret.
"""

from __future__ import annotations

import hashlib
import math
import unicodedata
from typing import Any, Final

# Quantization precision, in decimal places. See module docstring for rationale.
LENGTH_DECIMALS: Final = 6  # micrometre
VOLUME_DECIMALS: Final = 6
AREA_DECIMALS: Final = 6
RATIO_DECIMALS: Final = 9
ANGLE_DECIMALS: Final = 6
DEFAULT_DECIMALS: Final = 9

# Keys whose values are inherently non-reproducible. Matched case-insensitively
# as whole segments of a key path, so "created_at" is dropped but "created_at_utc"
# would be too; use VOLATILE_SUBSTRINGS for the looser case.
VOLATILE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "created_at",
        "updated_at",
        "generated_at",
        "timestamp",
        "started_at",
        "completed_at",
        "finished_at",
        "duration_seconds",
        "elapsed_seconds",
        "duration_ms",
        "uuid",
        "guid",
        "global_id",
        "globalid",
        "document_guid",
        "doc_guid",
        "owner_history",
        "temp_dir",
        "temp_path",
        "tmp_dir",
        "tmp_path",
        "output_dir",
        "output_path",
        "artifact_path",
        "storage_key",
        "object_key",
        "blob_key",
        "file_path",
        "filepath",
        "abs_path",
        "absolute_path",
        "working_directory",
        "cwd",
        "host",
        "hostname",
        "machine",
        "pid",
        "process_id",
        "job_id",
        "request_id",
        "trace_id",
        "database_id",
        "db_id",
        "row_id",
        "record_id",
        "entity_id",
        "user_id",
        "project_id",
        "alternative_id",
        "version_id",
        "revision_id",
        "python_version",
        "executable",
        "executable_path",
        "worker_root",
        "sys_version",
        "platform",
        "platform_machine",
        "freecad_root",
        "toolchain_manifest",
    }
)

# Substrings that mark a key as volatile even when embedded in a longer name,
# e.g. "freecad_document_guid" or "mesh_tmp_path".
VOLATILE_SUBSTRINGS: Final[tuple[str, ...]] = (
    "_guid",
    "guid_",
    "_uuid",
    "uuid_",
    "_timestamp",
    "timestamp_",
    "_temp",
    "temp_",
    "_tmp",
    "created_",
    "elapsed",
)

#: Collections whose element order carries no meaning. Their lists are sorted
#: before hashing, so regenerating the same design with its parts discovered in a
#: different order still yields the same hash.
#:
#: This is an explicit allowlist rather than a global "sort every list" rule,
#: because most lists in a geometry payload are order-significant: a footprint's
#: ``points`` define a ring, and reordering them changes the shape entirely.
#: Sorting those would make two genuinely different buildings collide.
UNORDERED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "elements",
        "masses",
        "parts",
        "members",
        "children",
        "storeys",
        "alternatives",
        "faces",
        "solids",
    }
)

# Non-finite floats cannot appear in canonical JSON and have no meaningful
# geometric value; they are treated as absent rather than silently coerced.
_TOLERANCE: Final = 1e-9


def _is_volatile(key: str) -> bool:
    """Return True when *key* names a field that must not affect the hash."""
    lowered = key.lower()
    if lowered in VOLATILE_KEYS:
        return True
    return any(marker in lowered for marker in VOLATILE_SUBSTRINGS)


def quantize(value: float, decimals: int = DEFAULT_DECIMALS) -> float:
    """Round *value* to *decimals* places, normalising negative zero away.

    ``-0.0`` and ``0.0`` compare equal in Python but serialise differently in
    JSON, which would silently split one geometry across two hashes.
    """
    rounded = round(float(value), decimals)
    if rounded == 0.0:
        return 0.0
    if not math.isfinite(rounded):
        raise ValueError(f"cannot canonicalize non-finite value: {value!r}")
    return rounded


def _number_decimals_for_key(key: str) -> int:
    """Choose a quantization precision appropriate to the quantity *key* names."""
    lowered = key.lower()
    if any(token in lowered for token in ("ratio", "fraction", "rate", "utilization")):
        return RATIO_DECIMALS
    if any(token in lowered for token in ("angle", "degrees", "rotation")):
        return ANGLE_DECIMALS
    if any(token in lowered for token in ("volume", "area", "length", "width", "depth", "height", "radius", "perimeter")):
        return AREA_DECIMALS
    return DEFAULT_DECIMALS


def _normalize_string(value: str) -> str:
    """Normalise Unicode so equivalent strings hash identically."""
    return unicodedata.normalize("NFC", value)


def canonicalize(value: Any, *, _key: str = "") -> Any:
    """Recursively normalise *value* into a canonical, hashable structure.

    Floats are quantized, ``-0.0`` is folded to ``0.0``, volatile keys are
    dropped, mappings are key-sorted by the caller, and non-finite floats raise
    rather than being silently coerced to a misleading number.
    """
    if value is None or isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite float in canonical input at {_key!r}: {value!r}")
        return quantize(value, _number_decimals_for_key(_key))

    if isinstance(value, str):
        return _normalize_string(value)

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key in value:
            key = str(raw_key)
            if _is_volatile(key):
                continue
            result[_normalize_string(key)] = canonicalize(value[raw_key], _key=key)
        return result

    if isinstance(value, (list, tuple)):
        items = [canonicalize(item, _key=_key) for item in value]
        if _key.lower() in UNORDERED_KEYS:
            # The order of these collections is not part of their meaning.
            return sorted(items, key=_sort_key)
        return items

    if isinstance(value, (set, frozenset)):
        # Sets have no intrinsic order; sort their canonical forms so membership,
        # not iteration order, determines the hash.
        return sorted((canonicalize(item, _key=_key) for item in value), key=_sort_key)

    raise TypeError(f"cannot canonicalize {type(value).__name__} at {_key!r}")


def _sort_key(value: Any) -> str:
    """Return a stable, type-tagged sort key for arbitrary canonical values."""
    if isinstance(value, dict):
        return "d:" + "|".join(f"{k}={_sort_key(value[k])}" for k in sorted(value))
    if isinstance(value, list):
        return "l:" + "|".join(_sort_key(item) for item in value)
    if isinstance(value, bool):
        return f"b:{int(value)}"
    if isinstance(value, (int, float)):
        return f"n:{value!r}"
    return f"s:{value!r}"


def canonical_json(value: Any) -> str:
    """Return the canonical JSON text for *value*.

    Separators are fixed and keys are sorted so that the same logical content
    always produces byte-identical output.
    """
    import json

    return json.dumps(
        canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def semantic_hash(value: Any) -> str:
    """Return the SHA-256 hex digest of the canonical form of *value*.

    >>> semantic_hash({"volume_m3": 1.0, "created_at": "2026-01-01T00:00:00Z"})
    '...'
    """
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def volumes_match(measured: float, expected: float, tolerance_ratio: float) -> bool:
    """Return True when *measured* is within *tolerance_ratio* of *expected*.

    The comparison is relative to the expected value so that the tolerance means
    the same thing for a 500 m3 core and a 40000 m3 tower. Non-positive expected
    values fall back to an absolute comparison to avoid dividing by zero.
    """
    if not math.isfinite(measured) or not math.isfinite(expected):
        return False
    if expected <= _TOLERANCE:
        return abs(measured - expected) <= _TOLERANCE
    return abs(measured - expected) / expected <= tolerance_ratio

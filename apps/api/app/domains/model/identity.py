from __future__ import annotations

import hashlib
import json
from typing import Any

from .schemas import ArchitecturalModel


def canonical_model_payload(model: ArchitecturalModel) -> dict[str, Any]:
    """Return the stable, serialization-ready representation used for identity."""
    return model.model_dump(mode="json", exclude_none=False)


def canonical_model_bytes(model: ArchitecturalModel) -> bytes:
    return json.dumps(
        canonical_model_payload(model),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def model_hash(model: ArchitecturalModel) -> str:
    """Return the SHA-256 identity of the complete canonical model state."""
    return hashlib.sha256(canonical_model_bytes(model)).hexdigest()

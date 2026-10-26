from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.domains.lifecycle.service import canonical_hash


@dataclass(frozen=True)
class CopilotContext:
    project_id: str
    version_id: str
    revision_hash: str
    payload: dict[str, Any]
    context_hash: str


def build_copilot_context(
    *,
    project_id: str,
    version_id: str,
    revision_hash: str,
    world_model: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]] = (),
    max_evidence: int = 20,
) -> CopilotContext:
    """Build the smallest deterministic context envelope for AI reasoning."""

    if not project_id.strip() or not version_id.strip() or not revision_hash.strip():
        raise ValueError("project, version, and revision identity are required")
    if max_evidence < 0:
        raise ValueError("max_evidence must be non-negative")

    normalized_evidence = [
        {
            "id": str(item.get("id", "")),
            "type": str(item.get("type", "")),
            "label": str(item.get("label", "")),
            "payload": item.get("payload", {}),
        }
        for item in evidence[:max_evidence]
    ]
    normalized_evidence.sort(key=lambda item: (item["type"], item["id"]))
    payload = {
        "schema_version": "1.0.0",
        "project_id": project_id.strip(),
        "version_id": version_id.strip(),
        "revision_hash": revision_hash.strip(),
        "world_model": dict(world_model),
        "evidence": normalized_evidence,
        "content_is_untrusted_data": True,
    }
    return CopilotContext(
        project_id=project_id.strip(),
        version_id=version_id.strip(),
        revision_hash=revision_hash.strip(),
        payload=payload,
        context_hash=canonical_hash(payload),
    )

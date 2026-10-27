from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from app.core.config import get_settings
from app.domains.lifecycle.service import canonical_hash
from app.domains.ai.proposals import AIProposal


@dataclass(frozen=True)
class ApprovalClaims:
    proposal_id: str
    project_id: str
    version_id: str
    base_revision_hash: str
    proposal_hash: str
    plan_fingerprint: str
    expires_at: int


def _encode(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(value: str) -> dict[str, object]:
    padding = "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode((value + padding).encode("ascii"))
    payload = json.loads(decoded)
    if not isinstance(payload, dict):
        raise ValueError("approval token payload must be an object")
    return payload


def _signature(value: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), value.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def issue_approval_token(
    proposal: AIProposal,
    plan_fingerprint: str,
    *,
    ttl_seconds: int = 600,
    now: int | None = None,
) -> str:
    if not plan_fingerprint.strip():
        raise ValueError("plan fingerprint is required")
    if not 1 <= ttl_seconds <= 3600:
        raise ValueError("approval token TTL must be between 1 and 3600 seconds")
    issued_at = int(time.time()) if now is None else now
    payload = {
        "v": 1,
        "proposal_id": proposal.proposal_id,
        "project_id": proposal.project_id,
        "version_id": proposal.version_id,
        "base_revision_hash": proposal.base_revision_hash,
        "proposal_hash": canonical_hash(proposal.model_dump(mode="json")),
        "plan_fingerprint": plan_fingerprint,
        "exp": issued_at + ttl_seconds,
    }
    encoded = _encode(payload)
    secret = get_settings().auth_secret
    return f"v1.{encoded}.{_signature(encoded, secret)}"


def verify_approval_token(token: str, *, now: int | None = None) -> ApprovalClaims:
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "v1":
        raise ValueError("INVALID_APPROVAL_TOKEN")
    encoded, provided_signature = parts[1], parts[2]
    expected = _signature(encoded, get_settings().auth_secret)
    if not hmac.compare_digest(provided_signature, expected):
        raise ValueError("INVALID_APPROVAL_TOKEN")
    payload = _decode(encoded)
    if payload.get("v") != 1:
        raise ValueError("INVALID_APPROVAL_TOKEN")
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int):
        raise ValueError("INVALID_APPROVAL_TOKEN")
    current = int(time.time()) if now is None else now
    if expires_at <= current:
        raise ValueError("APPROVAL_TOKEN_EXPIRED")
    required = (
        "proposal_id",
        "project_id",
        "version_id",
        "base_revision_hash",
        "proposal_hash",
        "plan_fingerprint",
    )
    if any(not isinstance(payload.get(field), str) or not str(payload[field]).strip() for field in required):
        raise ValueError("INVALID_APPROVAL_TOKEN")
    return ApprovalClaims(
        proposal_id=str(payload["proposal_id"]),
        project_id=str(payload["project_id"]),
        version_id=str(payload["version_id"]),
        base_revision_hash=str(payload["base_revision_hash"]),
        proposal_hash=str(payload["proposal_hash"]),
        plan_fingerprint=str(payload["plan_fingerprint"]),
        expires_at=expires_at,
    )

from __future__ import annotations

import hashlib
import json

from .schemas import CommandEnvelope


def canonical_payload(command: CommandEnvelope) -> str:
    return json.dumps(command.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(command: CommandEnvelope) -> str:
    return hashlib.sha256(canonical_payload(command).encode("utf-8")).hexdigest()


def command_fingerprint(command: CommandEnvelope) -> str:
    material = "|".join((command.project_id, command.version_id, command.type, str(command.schema_version), payload_hash(command)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()

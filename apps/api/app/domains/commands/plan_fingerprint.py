from __future__ import annotations

import hashlib
import json
from typing import Any

from .plan import CommandPlan


def fingerprint_plan(
    plan: CommandPlan,
    command_payloads: dict[str, dict[str, Any]],
    *,
    command_types: dict[str, str] | None = None,
    schema_versions: dict[str, int] | None = None,
) -> str:
    """Hash the plan graph and canonical command semantics deterministically."""
    plan.validate()
    types = command_types or {}
    versions = schema_versions or {}
    canonical = {
        "plan_id": plan.plan_id,
        "project_id": plan.project_id,
        "version_id": plan.version_id,
        "base_revision_hash": plan.base_revision_hash,
        "nodes": [
            {
                "node_id": node.node_id,
                "command_id": node.command_id,
                "depends_on": list(node.depends_on),
                "command_type": types.get(node.command_id),
                "schema_version": versions.get(node.command_id),
                "payload": command_payloads.get(node.command_id, {}),
            }
            for node in plan.nodes
        ],
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

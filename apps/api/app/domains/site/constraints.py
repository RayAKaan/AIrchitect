from __future__ import annotations

import hashlib
import json
from typing import Any

from app.db.site_models import SiteRevision

RUNNER_VERSION = "site-constraints-1.0.0"


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def detect_constraints(revision: SiteRevision, analysis: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = analysis.get("metrics", {}) if isinstance(analysis, dict) else {}
    warnings = analysis.get("warnings", []) if isinstance(analysis, dict) else []
    source_hash = str(analysis.get("source_context_hash", ""))
    constraints: list[dict[str, Any]] = []
    coverage = float(metrics.get("building_coverage_ratio", 0.0) or 0.0)
    if coverage >= 0.70:
        constraints.append({"type": "HIGH_EXISTING_COVERAGE", "severity": "HIGH", "status": "SUPPORTED", "value": {"coverage_ratio": coverage}, "message": "Existing building coverage is high relative to the site area."})
    if "NO_ROAD_CONTEXT" in warnings:
        constraints.append({"type": "ACCESS_UNKNOWN", "severity": "MEDIUM", "status": "UNKNOWN", "value": {}, "message": "No road context is available; vehicular access cannot be established."})
    if "NO_LAND_USE_CONTEXT" in warnings:
        constraints.append({"type": "LAND_USE_UNKNOWN", "severity": "MEDIUM", "status": "UNKNOWN", "value": {}, "message": "No land-use context is available."})
    if float(metrics.get("water_area_m2", 0.0) or 0.0) > 0:
        constraints.append({"type": "WATER_CONTEXT", "severity": "HIGH", "status": "SUPPORTED", "value": {"water_area_m2": metrics["water_area_m2"]}, "message": "Water context intersects the site."})
    return [{**item, "site_revision_hash": revision.content_hash, "source_context_hash": source_hash, "runner_version": RUNNER_VERSION, "idempotency_hash": _hash(item)} for item in constraints]

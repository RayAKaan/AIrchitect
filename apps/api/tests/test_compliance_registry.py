from __future__ import annotations

import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / "docs/legal/compliance-registry.json"


def test_compliance_registry_has_reviewed_dependency_records() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    dependencies = registry["third_party_dependencies"]

    assert dependencies
    assert all(item["classification"] in {"CORE", "INFRASTRUCTURE", "OPTIONAL", "EXPERIMENTAL", "REJECTED"} for item in dependencies)
    assert all(item["license"] not in {"", None, "UNKNOWN"} for item in dependencies)
    assert all(date.fromisoformat(item["review_due"]) >= date.today() for item in dependencies)


def test_data_source_registry_is_explicitly_separate_from_software() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    assert "third_party_dependencies" in registry
    assert "provider_terms" in registry
    assert "data_sources" in registry
    assert registry["data_sources"] == []

#!/usr/bin/env python3
"""Validate the machine-readable third-party/data compliance registry."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/legal/compliance-registry.json"

REQUIRED_DEPENDENCY_FIELDS = {
    "name", "version", "repository", "license", "copyright", "purpose", "runtime",
    "linking_mode", "modified", "data_dependencies", "commercial_restrictions", "replacement_strategy",
    "classification", "review_status", "review_owner", "review_date", "review_due", "evidence",
}
REQUIRED_CLASSIFICATIONS = {"CORE", "INFRASTRUCTURE", "OPTIONAL", "EXPERIMENTAL", "REJECTED"}
REQUIRED_DATA_FIELDS = {"name", "provider", "dataset", "license", "terms_url", "commercial_use", "attribution", "geographic_scope", "review_date", "review_due", "status"}
REQUIRED_PROVIDER_FIELDS = {"name", "capability", "terms_version", "license", "attribution", "commercial_use", "caching", "coverage", "review_date", "review_due", "status"}


def parse_date(value: str, field: str, errors: list[str]) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        errors.append(f"invalid {field}: {value!r}")
        return None


def main() -> int:
    try:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cannot read compliance registry: {exc}")
        return 1

    errors: list[str] = []
    if registry.get("schema_version") != "1.0":
        errors.append("unsupported registry schema_version")

    policy = registry.get("review_policy", {})
    for key in ("preferred_licenses", "review_licenses", "reject_by_default"):
        if not isinstance(policy.get(key), list):
            errors.append(f"review_policy.{key} must be a list")

    today = date.today()
    names: set[tuple[str, str]] = set()
    for dependency in registry.get("third_party_dependencies", []):
        missing = REQUIRED_DEPENDENCY_FIELDS - dependency.keys()
        errors.extend(f"dependency {dependency.get('name', '<unnamed>')} missing {field}" for field in sorted(missing))
        identity = (str(dependency.get("name")), str(dependency.get("version")))
        if identity in names:
            errors.append(f"duplicate dependency: {identity[0]} {identity[1]}")
        names.add(identity)
        if dependency.get("classification") not in REQUIRED_CLASSIFICATIONS:
            errors.append(f"dependency {identity[0]} has invalid classification")
        if dependency.get("license") in {None, "", "UNKNOWN"} and dependency.get("classification") != "REJECTED":
            errors.append(f"dependency {identity[0]} has unknown license")
        due = parse_date(dependency.get("review_due"), f"{identity[0]}.review_due", errors)
        if due and due < today and dependency.get("review_status") != "EXPIRED":
            errors.append(f"dependency {identity[0]} has stale review due {due.isoformat()}")

    for provider in registry.get("provider_terms", []):
        missing = REQUIRED_PROVIDER_FIELDS - provider.keys()
        errors.extend(f"provider {provider.get('name', '<unnamed>')} missing {field}" for field in sorted(missing))
        due = parse_date(provider.get("review_due"), f"{provider.get('name', '<unnamed>')}.review_due", errors)
        if due and due < today and provider.get("status") != "EXPIRED":
            errors.append(f"provider {provider.get('name')} has stale terms review due {due.isoformat()}")

    for source in registry.get("data_sources", []):
        missing = REQUIRED_DATA_FIELDS - source.keys()
        errors.extend(f"data source {source.get('name', '<unnamed>')} missing {field}" for field in sorted(missing))
        due = parse_date(source.get("review_due"), f"{source.get('name', '<unnamed>')}.review_due", errors)
        if due and due < today and source.get("status") != "EXPIRED":
            errors.append(f"data source {source.get('name')} has stale review due {due.isoformat()}")
        if source.get("license") in {None, "", "UNKNOWN"} and source.get("status") not in {"REJECTED", "PENDING_REVIEW"}:
            errors.append(f"data source {source.get('name')} has no explicit data license")

    for review in registry.get("license_reviews", []):
        due = parse_date(review.get("review_due"), "license_review.review_due", errors)
        if due and due < today:
            errors.append(f"license review for {review.get('scope')} is stale")

    if errors:
        print("FAIL: compliance registry validation")
        print("\n".join(f" - {error}" for error in errors))
        return 1

    print(
        "PASS: compliance registry valid "
        f"({len(registry.get('third_party_dependencies', []))} dependencies, "
        f"{len(registry.get('provider_terms', []))} providers, "
        f"{len(registry.get('data_sources', []))} data sources, "
        f"{len(registry.get('license_reviews', []))} license reviews)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

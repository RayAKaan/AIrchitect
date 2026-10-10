#!/usr/bin/env python3
"""Validate the committed CAD/BIM dependency inventory against reviewed policy.

Ordinary CI permits the exact, technically reviewed LGPL components in the policy.
It rejects unreviewed copyleft additions and dependencies with no licence identifier
and no recorded licence file. --release is intentionally stricter and fails until
legal clearance is explicitly recorded and metadata warnings have been resolved.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "apps/api/app/domains/cad/toolchain_manifest.json"
DEFAULT_POLICY = ROOT / "docs/legal/cad-license-policy.json"

RISKY_MARKERS = (
    "agpl",
    "gpl",
    "sspl",
    "busl",
    "commons clause",
    "mpl",
    "mozilla public license",
    "epl",
    "eclipse public license",
    "cddl",
)


def _markers(value: str) -> set[str]:
    """Find restrictive licence markers without misclassifying LGPL as GPL."""
    result: set[str] = set()
    for marker in RISKY_MARKERS:
        pattern = r"(?<![a-z0-9])" + re.escape(marker) + r"(?![a-z0-9])"
        if re.search(pattern, value, flags=re.IGNORECASE):
            result.add(marker)
    return result


def _component_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("package") or ""),
        str(row.get("version") or ""),
        str(row.get("license") or ""),
    )


def validate_manifest(
    manifest: dict[str, Any],
    policy: dict[str, Any],
    *,
    release: bool = False,
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for the manifest and its explicit policy."""
    errors: list[str] = []
    warnings: list[str] = []

    if manifest.get("schema_version") != "1.0":
        errors.append("unsupported or missing toolchain manifest schema_version")

    approved_rows = policy.get("approved_copyleft_components", [])
    approved = {_component_key(row): row for row in approved_rows if isinstance(row, dict)}
    if len(approved) != len(approved_rows):
        errors.append("licence policy contains malformed or duplicate approved component entries")

    packages = manifest.get("python_packages", {})
    package_rows: list[dict[str, Any]] = []
    for group in ("direct", "transitive"):
        rows = packages.get(group, [])
        if not isinstance(rows, list):
            errors.append(f"manifest python_packages.{group} must be a list")
            continue
        for row in rows:
            if not isinstance(row, dict):
                errors.append(f"manifest python_packages.{group} contains a malformed entry")
                continue
            package_rows.append(row)
            name = str(row.get("package") or "<unnamed>")
            version = str(row.get("version") or "")
            if not version:
                errors.append(f"{name}: version is missing")
            license_id = row.get("license_effective") or row.get("license")
            license_files = row.get("license_files") or []
            if not license_id and not license_files:
                errors.append(f"{name}@{version}: no licence identifier or recorded licence file")
            elif not license_id:
                warnings.append(
                    f"{name}@{version}: licence identifier unresolved; recorded licence file(s) require manual review"
                )

            marker_values = set(str(value).lower() for value in (row.get("copyleft_markers") or []))
            if license_id:
                marker_values |= _markers(str(license_id))
            non_lgpl = marker_values - {"lgpl"}
            if non_lgpl:
                errors.append(
                    f"{name}@{version}: unreviewed restrictive licence marker(s): {', '.join(sorted(non_lgpl))}"
                )

    inventory_rows = manifest.get("copyleft_components", [])
    if not isinstance(inventory_rows, list):
        errors.append("manifest copyleft_components must be a list")
        inventory_rows = []
    inventory_keys: set[tuple[str, str, str]] = set()
    for row in inventory_rows:
        if not isinstance(row, dict):
            errors.append("manifest copyleft_components contains a malformed entry")
            continue
        key = _component_key(row)
        if not all(key):
            errors.append(f"copyleft component has incomplete identity/licence: {key!r}")
            continue
        if key in inventory_keys:
            errors.append(f"duplicate copyleft component entry: {key!r}")
        inventory_keys.add(key)
        markers = {str(value).lower() for value in (row.get("markers") or [])}
        if markers - {"lgpl"}:
            errors.append(
                f"{key[0]}@{key[1]}: copyleft marker(s) require explicit policy review: {', '.join(sorted(markers - {'lgpl'}))}"
            )
        if key not in approved:
            errors.append(
                f"{key[0]}@{key[1]} ({key[2]}): copyleft component is not explicitly reviewed in {DEFAULT_POLICY.name}"
            )

    for row in package_rows:
        markers = {str(value).lower() for value in (row.get("copyleft_markers") or [])}
        if not markers:
            continue
        key = (
            str(row.get("package") or ""),
            str(row.get("version") or ""),
            str(row.get("license_effective") or row.get("license") or ""),
        )
        if key not in inventory_keys:
            errors.append(
                f"{key[0]}@{key[1]}: package metadata reports copyleft but the copyleft inventory has no matching entry"
            )

    required = {
        _component_key(row)
        for row in approved_rows
        if isinstance(row, dict) and row.get("required", True)
    }
    missing = required - inventory_keys
    for package, version, license_id in sorted(missing):
        errors.append(f"required reviewed component missing from manifest: {package}@{version} ({license_id})")

    if release:
        if not policy.get("commercial_release_approved", False):
            errors.append("commercial release is blocked: licence policy has not been approved")
        for blocker in policy.get("release_blockers", []):
            errors.append(f"commercial release blocker: {blocker}")
        if warnings:
            errors.append("commercial release is blocked while any licence metadata warnings remain")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument(
        "--release",
        action="store_true",
        help="apply strict commercial-release gates; expected to fail until legal/metadata blockers are closed",
    )
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cannot load manifest or policy: {exc}", file=sys.stderr)
        return 2

    errors, warnings = validate_manifest(manifest, policy, release=args.release)
    for warning in warnings:
        print(f"WARN: {warning}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(
        f"PASS: reviewed CAD/BIM licence policy; "
        f"{len(manifest.get('copyleft_components', []))} copyleft component(s) accounted for"
    )
    if not args.release:
        print("NOTE: this is a CI policy check, not legal clearance or commercial-release approval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

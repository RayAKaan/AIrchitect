"""Regression tests for the CAD/BIM dependency licence policy gate."""

from __future__ import annotations

import json
import runpy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CHECKER: dict[str, Any] = runpy.run_path(str(ROOT / "scripts/check_cad_toolchain_manifest.py"))
validate_manifest = CHECKER["validate_manifest"]


def _inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads(
        (ROOT / "apps/api/app/domains/cad/toolchain_manifest.json").read_text(encoding="utf-8")
    )
    policy = json.loads((ROOT / "docs/legal/cad-license-policy.json").read_text(encoding="utf-8"))
    return manifest, policy


def test_committed_toolchain_manifest_matches_reviewed_policy() -> None:
    manifest, policy = _inputs()
    errors, _warnings = validate_manifest(manifest, policy)
    assert errors == []


def test_unreviewed_copyleft_component_fails_closed() -> None:
    manifest, policy = _inputs()
    manifest["copyleft_components"].append(
        {
            "package": "unreviewed-native-kernel",
            "version": "9.9.9",
            "license": "GPL-3.0-only",
            "markers": ["gpl"],
            "group": "native-library",
        }
    )
    errors, _warnings = validate_manifest(manifest, policy)
    assert any("not explicitly reviewed" in error for error in errors)
    assert any("require explicit policy review" in error for error in errors)


def test_untraceable_dependency_fails_closed() -> None:
    manifest, policy = _inputs()
    dependency = manifest["python_packages"]["direct"][0]
    dependency["license"] = None
    dependency["license_effective"] = None
    dependency["license_files"] = []
    errors, _warnings = validate_manifest(manifest, policy)
    assert any("no licence identifier or recorded licence file" in error for error in errors)


def test_commercial_release_is_blocked_until_legal_clearance() -> None:
    manifest, policy = _inputs()
    errors, _warnings = validate_manifest(manifest, policy, release=True)
    assert any("licence policy has not been approved" in error for error in errors)
    assert any("commercial release blocker" in error for error in errors)

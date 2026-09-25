#!/usr/bin/env python3
"""Offline release preflight: verifies repository hygiene and required phase evidence."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md", ".env.example", "docker-compose.yml", "Makefile",
    "apps/api/pyproject.toml", "apps/api/app/main.py",
    "apps/web/package.json", "apps/web/src/main.tsx",
    "docs/implementation/PHASE-TRACKER.md",
    "docs/completion/MASTER_AUDIT.md",
    "docs/completion/BLUEPRINT_TRACEABILITY_MATRIX.md",
    "docs/completion/IMPLEMENTATION_GAPS.md",
]
PHASE_REPORTS = [f"docs/implementation/PHASE-{n}-{slug}.md" for n, slug in [
    (0,"REPOSITORY-AUDIT"),(1,"DEVELOPMENT-FOUNDATION"),(2,"IDENTITY-PROJECT-CORE"),
    (3,"WORLD-MODEL"),(4,"REQUIREMENTS-INTELLIGENCE"),(5,"ASSUMPTIONS-CLARIFICATIONS"),
    (6,"DECISION-RUNTIME"),(7,"WORKFLOW-RUNTIME"),(8,"GEOMETRY-ENGINE"),
    (9,"3D-VIEWER"),(10,"QUANTITIES-COST"),(11,"STRUCTURAL-WORKFLOW"),
    (12,"REGULATORY-ENGINE"),(13,"CHANGE-IMPACT"),(14,"VALIDATION-EVIDENCE"),
    (15,"REVIEW-DELIVERABLES"),(16,"FRONTEND-INTEGRATION"),
]]
missing = [p for p in REQUIRED + PHASE_REPORTS if not (ROOT / p).is_file()]
if missing:
    print("FAIL: missing required repository evidence:")
    print("\n".join(f" - {p}" for p in missing))
    sys.exit(1)

# Prevent accidental inclusion of local secrets and bulky/generated state in a release archive.
forbidden_dirs = {"node_modules", ".venv", "__pycache__", ".pytest_cache", "dist"}
for path in ROOT.rglob("*"):
    if any(part in forbidden_dirs for part in path.parts):
        continue
    if path.is_file() and path.name == ".env":
        print(f"FAIL: local secret file must not be included: {path.relative_to(ROOT)}")
        sys.exit(1)
    if path.is_file() and path.suffix in {".pyc", ".tsbuildinfo"}:
        print(f"WARN: generated/local file present: {path.relative_to(ROOT)}")

print(f"PASS: {len(REQUIRED)} core files and {len(PHASE_REPORTS)} phase reports present")
print("NOTE: this is a repository preflight only; it does not certify runtime, security, DB migrations, browser E2E, or production readiness.")

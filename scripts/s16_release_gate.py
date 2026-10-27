#!/usr/bin/env python3
"""Deterministic repository gate for the S16 product-completion boundary."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "apps/api/app/domains/ai/copilot_loop.py": "S16.1 Copilot loop",
    "apps/api/app/domains/ai/copilot_loop_routes.py": "S16.1 Copilot route",
    "apps/web/src/features/foundation/ArchitectWorkspace.tsx": "S16.2 workspace",
    "apps/web/src/features/foundation/WorkspaceFlow.tsx": "S16.2 workflow",
    "apps/web/src/features/foundation/workspaceEvents.ts": "S16.3 sync contract",
    "apps/web/src/features/foundation/VersionHistory.tsx": "S16.4 history",
    "apps/web/e2e/phase30-s16-acceptance.spec.ts": "S16.5 E2E acceptance",
    "apps/api/app/core/reliability.py": "S16.6 reliability",
    "docs/completion/S16-FINAL-RELEASE-AUDIT.md": "S16 release audit",
}

missing = [label for path, label in REQUIRED.items() if not (ROOT / path).is_file()]
if missing:
    print("FAIL: missing S16 release evidence:")
    print("\n".join(f" - {item}" for item in missing))
    sys.exit(1)

workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
if "phase30-s16-acceptance.spec.ts" not in workflow:
    print("FAIL: CI does not execute the S16 browser acceptance suite")
    sys.exit(1)

config = (ROOT / "apps/api/app/core/config.py").read_text(encoding="utf-8")
for marker in ("database_pool_size", "validate_production_settings", "CAD_ALLOW_LEGACY_ENGINE"):
    if marker not in config:
        print(f"FAIL: production safeguard missing: {marker}")
        sys.exit(1)

print(f"PASS: S16 release gate verified {len(REQUIRED)} required implementation artifacts and CI integration")

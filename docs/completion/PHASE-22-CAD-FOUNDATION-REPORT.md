# Phase 22 — CAD Foundation & Runtime Reliability Report

**Status:** Partial — implementation delivered in this PR; phase exit gates remain open.
**Branch:** `feat/phase-22-cad-foundation`
**Scope:** Licence policy enforcement, manifest correctness, native CAD smoke tooling, CI integration, and release-preflight evidence.

## Changes in this PR

- Added `docs/legal/cad-license-policy.json` with exact reviewed package/version/licence entries for IfcOpenShell, FreeCAD, and OCCT. The file explicitly records that commercial release is not approved.
- Added `scripts/check_cad_toolchain_manifest.py`, a deterministic policy gate that checks manifest schema, expected core components, exact copyleft allowlist entries, new restrictive licence markers, and licence traceability.
- Updated the manifest generator to record `license_effective` when a distribution's `License` field is empty, and corrected the committed IfcOpenShell copyleft entry to LGPL-3.0-or-later based on its existing LGPLv3+ classifier.
- Added `scripts/cad_toolchain_smoke.py` to probe the configured real worker and validate a known prism against analytical measurements and exported artifacts.
- Added tests for the current manifest, unreviewed copyleft additions, missing licence evidence, and strict release-mode blocking.
- Wired the licence gate into GitHub Actions and expanded release preflight to require Phase 22 artefacts.
- Added a third-party notice inventory that records the remaining legal and packaging blockers without misrepresenting them as resolved.

## What this does not claim

- The native CAD smoke command has **not** been run on the supported production host as part of this GitHub-hosted Linux CI workflow.
- Passing the static policy gate is not legal advice and is not commercial distribution approval.
- Required licence text packaging and qualified counsel's countersignature remain release blockers.
- This does not certify structural engineering or regulatory compliance.

## Verification

GitHub Actions run [#97](https://github.com/RayAKaan/AIrchitect/actions/runs/38077005274) passed all four jobs on the initial PR commit:

- API: Ruff passed; **393 passed, 40 skipped, 2 warnings**; PostgreSQL migration upgrade/downgrade/upgrade passed; API Docker build passed.
- Web: lint passed; **4 test files / 17 tests passed**; production build and web Docker build passed.
- Docker Compose: all images built; stack started; database-aware `/ready` and API smoke checks passed; teardown passed.
- Release preflight and the new CAD/BIM licence-policy gate passed.

The follow-up commit also adds a Python syntax compilation gate for both CAD tooling scripts; its own CI run must pass before this PR is considered fully verified. Native-host smoke evidence must be attached separately before Phase 22 can be marked delivered.

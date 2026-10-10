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

The pull request's required GitHub Actions checks are the source of truth for code-level verification. Record the actual run URL and result here after CI completes. Native-host smoke evidence must be attached separately before Phase 22 can be marked delivered.

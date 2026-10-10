# Phase 28 — Complete Designer Workspace & Release Validation Report

**Status:** Implementation committed; final CI verification pending.
**Branch:** `feat/phase-28-workspace-release-validation`
**Pull request:** Pending creation after the implementation commit.

## Delivered in this phase

- Added a Foundation **Change Impact** tab connected to the persisted, version-scoped Phase 27 graph and existing optimistic-hash-guarded propagation API.
- Added a **Release Validation** checklist that correlates the canonical version, requirement-quality status, semantic model hash/consistency, CAD/BIM export manifest, and dependency graph integrity.
- Missing exports or empty dependency graphs are explicitly **NOT RUN**. Unavailable endpoints remain **UNKNOWN**. Stale hash bindings and cross-scope edges require review.
- Native CAD-host smoke and legal redistribution clearance remain **NOT VERIFIED** manual gates, so an otherwise green automated checklist cannot claim full release readiness.
- Added focused release-checklist model tests and a Playwright browser journey for registration through canonical brief/commit, semantic model, exports, dependency graph, and release validation.
- Added a CI browser-e2e job with Chromium installation and failure diagnostics; made Phase 28 UI/test/docs required by offline release preflight.
- Corrected Phase 26/27 plan/report text that incorrectly said their PRs were still open after merge.

## Verification

Final GitHub Actions CI evidence will be recorded here after the browser-e2e and full existing CI matrix finish on the PR head.

## Limitations and remaining gates

- Browser E2E and hosted CI validate the test environment, not native CAD tools on the target deployment host.
- Export checks are structural/integrity checks and do not prove round-trip behaviour in all target applications.
- Dependency propagation is explicit stale marking, not automatic recomputation.
- Structural output remains conceptual; regulatory `UNKNOWN` is not a pass.
- Complete redistribution/source-material notices and qualified legal sign-off remain separate release blockers.

**Merge status:** The Phase 28 PR will remain open for your review; it will not be merged automatically.

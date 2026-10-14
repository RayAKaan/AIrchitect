# Phase 28 — Complete Designer Workspace & Release Validation Report

**Status:** Implemented; PR #10 is open for review and CI run #375 passed.
**Branch:** `feat/phase-28-workspace-release-validation`
**Pull request:** https://github.com/RayAKaan/AIrchitect/pull/10

## Delivered in this phase

- Added a Foundation **Change Impact** tab connected to the persisted, version-scoped Phase 27 graph and existing optimistic-hash-guarded propagation API.
- Added a **Release Validation** checklist that correlates the canonical version, requirement-quality status, semantic model hash/consistency, CAD/BIM export manifest, and dependency graph integrity.
- Missing exports or empty dependency graphs are explicitly **NOT RUN**. Unavailable endpoints remain **UNKNOWN**. Stale hash bindings and cross-scope edges require review.
- Native CAD-host smoke and legal redistribution clearance remain **NOT VERIFIED** manual gates, so an otherwise green automated checklist cannot claim full release readiness.
- Added focused release-checklist model tests and a Playwright browser journey for registration through canonical brief/commit, semantic model, exports, dependency graph, and release validation.
- Added a CI browser-e2e job with Chromium installation and failure diagnostics; made Phase 28 UI/test/docs required by offline release preflight.
- Corrected Phase 26/27 plan/report text that incorrectly said their PRs were still open after merge.

## Verification

**Final GitHub Actions run:** [#375](https://github.com/RayAKaan/AIrchitect/actions/runs/38086482551) — all jobs passed on commit `48500fe5f8346f41506886e46eca8c3259b09b8f`.

- Backend: **449 passed, 40 skipped**, 2 warnings; Ruff and PostgreSQL migration upgrade/downgrade/upgrade checks passed.
- Frontend: **21 tests passed** across 5 test files; lint and production build passed.
- Browser acceptance: **1 Playwright test passed** across the end-to-end Foundation workflow.
- Docker API image and web image builds passed; Docker Compose startup/readiness/API smoke/teardown passed.
- Release preflight passed; CAD/BIM licence policy passed with 3 copyleft components accounted for.
- Requirements benchmark passed **10/10 exact-match cases**, precision **1.0000**, recall **1.0000**, F1 **1.0000**. These scores apply only to the committed ten-case fixture corpus.

## Limitations and remaining gates

- Browser E2E and hosted CI validate the test environment, not native CAD tools on the target deployment host.
- Export checks are structural/integrity checks and do not prove round-trip behaviour in all target applications.
- Dependency propagation is explicit stale marking, not automatic recomputation.
- Structural output remains conceptual; regulatory `UNKNOWN` is not a pass.
- Complete redistribution/source-material notices and qualified legal sign-off remain separate release blockers.

**Merge status:** PR #10 is open, mergeable status pending GitHub's final refresh, and not merged. Review and merge it manually.

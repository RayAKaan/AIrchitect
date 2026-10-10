# Phase 28 — Complete Designer Workspace & Release Validation

**Status:** Implementation in progress on `feat/phase-28-workspace-release-validation`.
**Base:** `main` after Phase 27 merge commit `bb6a1b491cd7d4908a1f3ce3288793507a16a34e`.

## Objective

Close the remaining cross-phase workspace integration gap and add an honest, version-bound release evidence checklist. Phase 28 is the final planned phase in the current 22–28 roadmap, but completion of this implementation does not automatically mean the product is cleared for commercial production.

## Repository-grounded findings

- The Foundation workspace already integrates the canonical brief/requirements flow, semantic editor (Phases 24–25), and validated CAD/BIM export manifest (Phase 26).
- Phase 27 exposes an authenticated persisted dependency graph and hash-guarded propagation API, but the Foundation workspace has no first-class view for that graph or action.
- Release evidence is spread across requirement validation, semantic model consistency, CAD/BIM manifest and dependency graph endpoints. No single screen summarizes whether those sources agree on the selected version/hash.
- Existing CI runs backend tests, frontend unit tests/build, Docker/Compose smoke, licensing policy and requirement benchmark, but did not execute a real browser acceptance test.
- Native CAD-host smoke and legal redistribution/source-material clearance are known external/manual gates; hosted CI cannot honestly infer them.

## Work packages

1. **Persisted dependency workspace:** Add a Foundation tab that loads only the server-authoritative version-scoped graph, renders its nodes/edges and cross-scope integrity status, and calls the existing hash-guarded propagation endpoint without accepting client-supplied topology.
2. **Release evidence checklist:** Aggregate the selected version status, requirement quality report, semantic model hash/consistency findings, export manifest hash/exportability, and dependency graph integrity. Missing evidence remains `NOT_RUN` or `UNKNOWN`, never silently PASS.
3. **Manual gates:** Display native deployment-host CAD smoke and legal redistribution clearance as `NOT_VERIFIED` until evidence is supplied by an appropriate external process. A licence-policy pass is not legal approval.
4. **Browser acceptance:** Add a Playwright journey covering registration, project creation, brief extraction, canonical commit, semantic-model inspection, empty export manifest, dependency graph, and release checklist.
5. **CI and release preflight:** Run the Phase 28 browser acceptance in GitHub Actions; require its test and the Phase 28 plan/report in offline release preflight.
6. **Cross-phase documentation alignment:** Correct Phase 26/27 documents that still say their merged PRs are open; update the phase tracker and record limitations.

## Acceptance criteria

- [x] Phase 27 graph and propagation APIs are accessible from the Foundation workspace without changing their server-side authorization/hash guards.
- [x] Release checklist compares source hashes and reports missing exports/graph data as not run, not as success.
- [x] Native CAD-host and legal gates remain explicitly unverified until deployment/legal evidence exists.
- [x] Browser acceptance covers the cross-phase Foundation workflow and is required by CI.
- [x] Unit tests cover current/stale hash binding, missing evidence, cross-scope findings, and the manual-gate override of an otherwise green automated result.
- [ ] GitHub Actions CI passes on the final PR head; record the exact run and test counts after execution.

## Boundaries

- Dependency propagation marks affected outputs stale; it does not recompute them or schedule work.
- CAD export structure/hash checks are not proof of universal round-trip interoperability.
- This checklist does not certify architecture, structural adequacy, zoning/building-code compliance, fire/life safety, accessibility, or constructability.
- Phase 22 native-host smoke verification and complete third-party notices/source materials plus qualified legal sign-off remain open release gates.

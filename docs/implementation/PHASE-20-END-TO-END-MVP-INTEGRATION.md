# Phase 20 — End-to-End MVP Integration

**Status:** In progress  
**Scope:** Connect the existing canonical brief, World Model, design, CAD/BIM, engineering, evidence, and human-review systems into one usable feasibility journey.  
**Safety boundary:** Outputs remain preliminary feasibility artifacts. Structural results are conceptual, missing authoritative regulatory evidence remains `UNKNOWN`, and human review is mandatory.

## Current-state finding

The repository already has a browser workspace for briefs, requirements, assumptions, World Model commits, design alternatives, CAD generation, engineering panels, evidence, workflow status, and review. The feasibility workflow also persists its tasks and evidence.

The integration gap is that the workflow's engineering task previously called the engineering resolver directly. Phase 19 correctly made that resolver require a validated `CAD_BREP`, but the workflow's own earlier tasks generated design alternatives without necessarily generating CAD. As a result, a user could run the feasibility workflow from the UI and receive a failure unless CAD had been generated separately beforehand.

## Phase 20 implementation in this PR

- Make the feasibility workflow ensure authoritative CAD exists for its selected alternative before engineering calculations.
- Reuse only the newest CAD artifact when it is current and its World Model hash and design hash match the selected alternative.
- If no matching current solid exists, run the configured isolated CAD worker and request a GLB artifact for the interactive viewer.
- Fail closed when CAD is disabled, the worker/toolchain is unavailable, the CAD job fails, or no validated geometry artifact is produced. Do not fall back to legacy GeometryIR.
- Keep engineering source selection centralized in `resolve_sources`, preserving validation, tenant/version binding, and stale-dependency checks.
- Record CAD run/artifact IDs and whether geometry was generated or reused in the persisted engineering workflow-step result.
- Add an API-level regression test that runs from a committed brief through design generation, CAD, engineering, evidence assembly, and a human review decision using the repository's real API and subprocess-based fake CAD worker.
- Invalidate frontend design/geometry/engineering queries after a workflow run so the workspace does not continue showing stale cached results.
- Show CAD-generation/reuse information in the workflow timeline.

## Verification and definition of done

- [ ] Ruff and API test suite pass.
- [ ] The end-to-end integration test proves the workflow reaches `WAITING_HUMAN_REVIEW`, the engineering step succeeds with a persisted CAD run, evidence exists, and a review decision completes the workflow.
- [ ] Frontend lint, unit tests, and production build pass.
- [ ] API and web Docker builds, Docker Compose health/smoke tests, and release preflight pass in GitHub Actions.
- [ ] Review CI logs and address any regression before calling the phase ready.

## Known boundaries

- CI uses a subprocess-based fake CAD worker for deterministic integration coverage; this does not prove that a particular production deployment has FreeCAD/OCCT/IfcOpenShell installed or configured.
- CAD solids are conceptual massing, not construction-ready BIM or certified engineering.
- The regulatory evaluator can return `UNKNOWN` when authoritative jurisdictional rules are unavailable.
- This PR closes the workflow's missing CAD handoff. It does not by itself finish all remaining Phase 19 legacy-path retirement or the broader production-hardening/release scope.

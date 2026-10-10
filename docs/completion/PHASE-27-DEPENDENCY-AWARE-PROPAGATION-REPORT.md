# Phase 27 — Dependency-Aware Feasibility & Change Propagation

**Status:** Implementation in progress; final CI evidence will be recorded after the PR head is verified.
**Branch:** `feat/phase-27-dependency-aware-propagation`
**Base:** `main`

## Intended delivery

- Make the persisted `ArtifactVersion` / `ArtifactDependency` graph authoritative for impact analysis.
- Calculate deterministic transitive dependency paths and reject cross-scope edges from traversal.
- Propagate stale state atomically to artifact rows, domain projections, deliverables, and CAD runs when the canonical World Model hash changes.
- Guard explicit propagation with project/version authorization and an expected-current-World-Model hash.
- Record audit events without mutating immutable artifact payloads or claiming recomputation.
- Add regression tests, phase documentation, tracker updates, and release-preflight enforcement.

## Verification

Final API, frontend, database migration, Docker/Compose smoke, licence-policy, benchmark, and release-preflight results will be added here after the PR head's GitHub Actions run completes.

## Limits

Passing automated tests does not establish native production-host CAD execution, full CAD/BIM round-trip compatibility, structural adequacy, or regulatory compliance. Phase 22's native-host and legal clearance gates remain separate.

# Phase 14 — Validation & Evidence (Partial)

## Delivered
- Typed validation request/check/evidence/response contracts.
- Duplicate check/evidence ID rejection.
- Deterministic aggregation of passed, failed, unknown checks.
- Evidence reference checks; absent or unverified evidence is reported as missing.
- Source-hash/current-hash comparison; mismatches force `stale` status.
- Explicit statuses: `ready_for_review`, `blocked`, `stale`, `incomplete`.
- Authenticated, project-membership-scoped `POST /api/v1/validation/evaluate` endpoint.
- Tests for review readiness caveat, stale hash, unknown blockers, unverified evidence, and human review.

## Status semantics
`ready_for_review` means only that supplied checks/evidence meet this evaluator's declared gates. It is not approval, certification, or permission to construct. Caller-supplied `verified` flags are not independently authenticated.

## Verification
`pytest -q`: 54 passed; 4 pre-existing FastAPI `on_event` deprecation warnings.

## Remaining
- Persist immutable validation runs and evidence records.
- Independently verify evidence/document hashes and access controls.
- Bind evaluation to persisted artifact, World Model, and ruleset revisions.
- Integrate all domain validators and change-impact stale propagation.
- Add PostgreSQL integration, tamper-evidence/audit trail, and frontend review UI.

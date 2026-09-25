# Phase 5 — Assumptions & Clarifications

## Implemented
- Persisted assumption records scoped to organization and project.
- Explicit `proposed`, `accepted`, `rejected`, and `replaced` lifecycle states.
- Assumption fields: parameter, value, unit, reason, source, impact scope, confidence, creator, project version, timestamp, and superseded record.
- Authenticated list/create/transition/replace endpoints under `/api/v1/projects/{project_id}/assumptions`.
- Mutations require an editable organization role and emit audit events.
- Only proposed assumptions can be accepted/rejected. Proposed or accepted assumptions may be replaced; replacement preserves the old record and links the new one.
- Acceptance/rejection increments project version; replacement increments project version and retains lineage.

## API
- `GET /api/v1/projects/{project_id}/assumptions`
- `POST /api/v1/projects/{project_id}/assumptions`
- `POST /api/v1/projects/{project_id}/assumptions/{assumption_id}/transition`
- `POST /api/v1/projects/{project_id}/assumptions/{assumption_id}/replace`

## Verification
- API test suite: 13 passed.
- Existing FastAPI `on_event` deprecation warnings remain.

## Limitations / open gates
- PostgreSQL-backed endpoint integration tests were not run in this environment.
- Assumption mutations increment the project version, but they do not yet create a unified World Model revision or automatically invoke dependency stale-propagation. That integration belongs in the version/change-impact implementation and must be completed before relying on downstream artifact freshness.
- Clarification question generation and frontend assumption management remain to be integrated.

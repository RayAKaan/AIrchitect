# Phase 7 — Workflow Runtime (partial)

## Implemented
- SQLAlchemy workflow and task persistence models.
- Authenticated, organization-scoped workflow creation and retrieval.
- Idempotency key scoped to organization; repeated submissions return the existing workflow.
- DAG schema validation: unique task keys, known/non-self dependencies, duplicate-dependency rejection, cycle detection.
- Dependency-aware ready-task claiming; downstream tasks are blocked until dependencies succeed.
- Persisted attempt counters, bounded retry-by-requeue on task failure, task success result persistence, and workflow cancellation.
- Terminal workflow guard for claim/cancel and state-derived workflow status.
- Five DAG validation tests.

## API
- `POST /api/v1/workflows`
- `GET /api/v1/workflows/{workflow_id}`
- `POST /api/v1/workflows/{workflow_id}/claim`
- `POST /api/v1/workflows/{workflow_id}/tasks/{task_id}/succeed`
- `POST /api/v1/workflows/{workflow_id}/tasks/{task_id}/fail`
- `POST /api/v1/workflows/{workflow_id}/cancel`

## Important limits / not yet production-ready
- Claiming currently uses ordinary ORM read/modify/write; concurrent workers are not protected by PostgreSQL row locks or atomic `UPDATE … RETURNING`. Do not run competing production workers against this implementation.
- Idempotency keys return the existing workflow, but request-body fingerprint comparison is not implemented; reuse of a key with a different payload must be addressed before production.
- Retry delay/backoff, lease expiry, worker heartbeat, crash recovery/reaper, durable event history, and cancellation of an already-running external side effect are not implemented.
- This phase defines orchestration state only. It does not execute task handlers or claim domain work has completed.
- PostgreSQL integration/migration execution was not verified in this environment.

## Validation
- `pytest -q`: 23 passed; 4 existing FastAPI lifecycle deprecation warnings.
- Unit tests cover valid DAG, duplicate keys, unknown dependencies, cycles, and self-dependency.

## Exit status
**Partial.** Durable schema and basic state-transition API exist. Atomic claiming, idempotency fingerprinting, recovery semantics, integration tests, and worker execution remain open.

# Phase 3 — Canonical Building World Model

## Status: Partially complete

### Implemented
- Pydantic v2 contracts for site, dimensions, levels, spaces, structural grid, provenance, and model snapshots.
- Domain validation for positive dimensions/grid spacing, unique IDs, and valid space-to-level references.
- Persistent `world_model_revisions` table storing immutable JSON snapshots with organization/project scope.
- Authenticated, membership-checked API routes to read current model, create a revision, and list revision history.
- Project version is incremented on accepted model mutation; caller supplies expected version and stale writes are rejected.
- Audit event emitted for accepted World Model revisions.
- Tests for empty model, references, duplicate IDs, positive dimensions, and provenance bounds.

### API
- `GET /api/v1/projects/{project_id}/world-model`
- `PUT /api/v1/projects/{project_id}/world-model` — body: `{ "expected_project_version": N, "model": { ... } }`
- `GET /api/v1/projects/{project_id}/world-model/revisions`

### Verification
- `pytest -q`: **10 passed** (includes existing Phase 1/2 tests and Phase 3 schema tests).
- Database-backed route/migration tests were not run because a live PostgreSQL service is not available in this execution environment.

### Known limitations / follow-up
- Snapshot storage currently uses SQLAlchemy JSON; production PostgreSQL migration and transaction/concurrency integration tests remain required.
- Project version check is application-level; harden with an atomic conditional update/row lock to eliminate concurrent-write race before production.
- World Model field-level provenance is represented on key objects and a provenance map; coverage should expand as domain fields mature.
- Schema creation in local mode is inherited from the foundation; production must use Alembic migrations.
- No downstream dependency invalidation yet; scheduled for Phase 13.

### Definition of Done assessment
Typed model, basic domain validation, authenticated mutation/read, revision history, and unit tests are implemented. Full database concurrency, migration, and tenant-isolation integration verification remain open; therefore Phase 3 is not declared fully complete.

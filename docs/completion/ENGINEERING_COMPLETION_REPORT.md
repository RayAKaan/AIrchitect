# Integrated MVP engineering report

Date: 2026-09-25

## 1. Baseline audit

The repository started as a 687 KB, single-commit modular-monolith prototype. It already contained FastAPI authentication/project endpoints, a partial SQLAlchemy model, deterministic requirement/geometry/cost/structure/regulatory/validation functions, a basic task-DAG API, review/PDF code, 58 documented unit tests, and a React/Vite workspace. The source showed that most engineering endpoints accepted caller-owned inputs and returned transient JSON. There was no `project_versions` table, artifact registry/dependency graph, persistent domain outputs, migration, frontend lockfile, or real WebGL viewer. Workflow claims were race-prone. Local startup used `create_all`. The canvas viewer was a 2D projection.

Baseline execution in this environment found documentation drift:

- Python install succeeded, but test collection failed because `reportlab` was imported but undeclared.
- Frontend `npm install` failed against the unpinned `latest` dependency set (`edgesOut` npm error).
- Docker/PostgreSQL baseline could not run because Docker is unavailable in this environment.
- Repository preflight passed its limited file-presence check.

## 2. Implemented changes

A connected canonical vertical slice now persists:

`Project -> ProjectVersion -> Requirements/Assumptions -> WorldModelRevision -> 3 Alternatives -> Geometry -> Quantities -> Costs -> Structural Concepts -> Regulatory UNKNOWN -> Validation -> Evidence -> Review-gated Deliverable`.

A floor-count change creates a new immutable project version and World Model revision, marks prior downstream artifacts/deliverables stale, emits a selective rerun plan, and permits generation/review of a new package while retaining version 1.

The primary production path resolves all calculations from canonical persisted state. Demo cost data is explicitly marked non-authoritative. Structural output remains `concept_only`; absent authoritative regulations remain `UNKNOWN` and block validation/review readiness.

## 3. Added modules/files

- `apps/api/app/domains/lifecycle/{schemas,service,routes}.py`
- `apps/api/alembic.ini`
- `apps/api/alembic/env.py`
- `apps/api/alembic/versions/20260925_0001_initial_integrated_mvp_schema.py`
- `apps/api/tests/test_integrated_lifecycle.py`
- `apps/web/package-lock.json`
- `apps/web/src/vite-env.d.ts`
- this report

## 4. Database/migrations

The initial Alembic baseline covers 30 tables, including identity/tenancy, projects and immutable versions, requirements, assumptions, World Models, generic artifact versions and dependency edges, alternatives, geometry, quantities, rates, costs, structural/regulatory/validation/evidence/decision records, durable workflow tasks/events, reviews, deliverables, and audit events. Application startup no longer invokes `Base.metadata.create_all`; Docker startup runs `alembic upgrade head`.

## 5. API changes

Canonical lifecycle APIs were added under `/api/v1` for project versions, brief persistence, version snapshots, demo rate schedules, workflow execution/events, versioned changes and impact, exact-version review, and JSON/PDF deliverables. Tenant checks are applied before lifecycle reads/writes. Project creation now creates version 1 transactionally.

## 6. Frontend

Dependencies are pinned and a lockfile is committed. The geometry inspector now uses Three.js through React Three Fiber and Drei. It fetches persisted snapshot geometry rather than accepting arbitrary dimensions. It supports orbit, pan, zoom, fit-to-view, alternative switching, floor visibility, loading/empty/error states, dimensions, hashes and stale/current status. Vite proxies `/api` for same-origin preview/development.

## 7. Workflow/runtime

The feasibility workflow persists 12 required stages and transition events. Generic task claims now use row locks with `SKIP LOCKED`, owners, leases, lease-expiry recovery, heartbeat timestamps, bounded exponential retry delay and explicit blocked/stale states. Pipeline runs are idempotent by organization/key and work with the deterministic decision provider (JEV disabled).

## 8. Artifact/version lineage

Every generated output has organization, project, project version, World Model revision, artifact type/version, status, actor, timestamp, canonical input references, provenance and SHA-256 output hash. Server-generated dependency edges connect alternatives through geometry/quantity/cost and geometry through structure/regulatory/validation/deliverable.

## 9–10. Verification and exact results

- Backend: **67 passed** (`pytest -q`).
- Ruff: **passed** (`ruff check .`).
- Alembic baseline: **upgrade succeeded**, current revision `20260925_0001` (verified with SQLite because Docker/PostgreSQL is unavailable).
- Frontend TypeScript check: **passed**.
- Frontend Vitest: **passed, 0 test files** (no browser test suite exists yet).
- Frontend production build: **passed**, 649 modules transformed.
- HTTP smoke E2E against the running API: register -> project -> brief (6 persisted requirements) -> World Model -> demo rate -> 12-stage workflow -> 20 artifact versions -> human review -> 5,247-byte PDF -> floor count change 4 to 6 -> v1 stale propagation -> v2 selective rerun -> 20 new artifact versions -> v2 review -> v2 JSON package. **Passed**.

## 11. Known limitations

This is an integrated MVP vertical slice, not production completion. PostgreSQL/PostGIS execution and lock-contention behavior were not verified because Docker is unavailable. Browser automation/E2E, SSE, generated OpenAPI client, file/object storage, OpenTelemetry export, password reset/session revocation, and authoritative Saudi rules/rates remain open. The frontend project workspace still does not expose every lifecycle panel. Quantity and structure engines are deliberately rectangular/conceptual. The initial migration contains explicit Alembic table/index/constraint operations; future schema changes require additional reviewed revisions. Frontend bundle size has a warning and needs code splitting. Legacy prototype endpoints still exist for compatibility and should be deprecated after clients move to canonical lifecycle APIs.

## 12. External credentials/services

None are required for deterministic MVP operation. JEV is optional and disabled by default. Production requires PostgreSQL/PostGIS, managed secrets, and any authoritative regulatory/rate evidence supplied and reviewed by qualified parties.

## 13. Run locally

```bash
cp .env.example .env
# Set a unique AUTH_SECRET
docker compose up --build
# Web: http://localhost:5173  API docs: http://localhost:8000/docs
```

Without Docker, for development only:

```bash
cd apps/api
pip install -e '.[dev]'
DATABASE_URL=sqlite+aiosqlite:///./dev.db alembic upgrade head
DATABASE_URL=sqlite+aiosqlite:///./dev.db uvicorn app.main:app --reload
# another shell
cd apps/web && npm ci && npm run dev
```

## 14. Full verified checks

```bash
cd apps/api && pytest -q && ruff check .
cd apps/web && npm ci && npm run lint && npm test && npm run build
cd apps/api && alembic upgrade head && alembic current
```

## 15. Definition-of-Done verification

The canonical deterministic vertical slice and the 4-to-6-floor version/change path were exercised successfully, including JSON/PDF and review. It works with JEV disabled. The broad repository-level definition is **not claimed fully complete** because PostgreSQL concurrency, browser E2E, complete frontend lifecycle coverage, and authoritative Saudi external data were not verified. No unverified engineering, regulatory, or market-data claim is represented as authoritative.

# Building feasibility platform

An AI-native, deterministic-first platform for versioned preliminary commercial/retail building feasibility. The product name is intentionally not fixed.

## Current implementation

Phase 1 establishes the canonical building brain:

`Organization -> Project -> Project Version -> Brief -> Requirements/Assumptions -> hash-verified World Model Revision`

See [the Phase 1 report](docs/completion/PHASE-1-COMPLETION-REPORT.md) and [source audit](docs/implementation/PHASE-1-COMPLIANCE-AUDIT.md). Later-phase prototype modules remain in the repository, but direct client-owned canonical geometry and legacy project-scoped mutations are disabled until those consumers are refactored onto the central World Model resolver.

Important boundaries:

- Structural output is conceptual and never certification.
- Missing authoritative regulatory evidence produces `UNKNOWN`, never `PASS`.
- Seeded demo rates are explicitly non-authoritative.
- JEV is optional; deterministic operation is the default.
- Historical project versions and artifact hashes remain inspectable.

See [the engineering report](docs/completion/ENGINEERING_COMPLETION_REPORT.md) for verified results and remaining limitations.

## Stack

- API: FastAPI, async SQLAlchemy, PostgreSQL/PostGIS direction, Alembic
- Web: React, TypeScript, Vite, TanStack Query, Three.js, React Three Fiber
- Workflow: persisted tasks/events, idempotency, leases, retries and PostgreSQL `SKIP LOCKED` claims

## Local run with Docker

```bash
cp .env.example .env
# Set a unique AUTH_SECRET in .env
docker compose up --build
```

- Web: http://localhost:5173
- API/OpenAPI: http://localhost:8000/docs

The API container runs `alembic upgrade head` before serving. Application startup never creates tables implicitly.

## Checks

```bash
cd apps/api && pip install -e '.[dev]' && pytest -q && ruff check .
cd apps/web && npm ci && npm run lint && npm test && npm run build
```

## Development without Docker

```bash
cd apps/api
pip install -e '.[dev]'
DATABASE_URL=sqlite+aiosqlite:///./dev.db alembic upgrade head
DATABASE_URL=sqlite+aiosqlite:///./dev.db uvicorn app.main:app --reload

# separate shell
cd apps/web
npm ci
npm run dev
```

SQLite is only a local/test convenience. PostgreSQL is the intended deployed database.

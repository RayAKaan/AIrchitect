# AIrchitect

AI-native architectural feasibility and design orchestration platform. The system is deterministic-first: AI can interpret and propose, while canonical project state is persisted, versioned and validated by domain logic.

## Current implementation

The current vertical slice establishes:

`Organization -> Project -> Project Version -> Brief -> Requirements/Assumptions -> World Model Revision -> Versioned Artifacts -> Dependency/Change Impact -> Validation/Release Checks`

Phase 27 established the authoritative artifact dependency graph and hash-guarded stale propagation. Phase 28 added workspace dependency/change-impact visibility and release validation.

The complete roadmap is intentionally incremental. Site World Model, provider-backed site analysis, program/concept generation, universal commands, complete semantic building model, drawing compiler, full analysis/review, BIM/CAD round-trip, collaboration and production scaling are **not** represented as complete merely because supporting infrastructure exists.

## Architectural rules

- Canonical World Model/revisions are authoritative; UI, maps, renderers, drawings, analyses, exports and boards are projections/derived artifacts.
- Derived artifacts retain source revision/hash and dependency lineage and can become stale.
- AI proposals cannot directly mutate canonical state.
- Evidence-backed factual claims retain source/date/dataset/scope/method/confidence/status/revision lineage; unknown remains `UNKNOWN`.
- Coordinate systems and units are explicit; display coordinates are not calculation authority.
- Existing Phase 27 dependency infrastructure is authoritative and must be reused for future regeneration.
- Professional claims such as structural, fire, regulatory or certification approval require appropriate authoritative evidence and human/professional review.

## Architecture truth

The S0 repository-truth contract is documented in:

- [Architecture overview](docs/architecture/overview.md)
- [State ownership](docs/architecture/state-ownership.md)
- [Coordinate systems](docs/architecture/coordinates.md)
- [Evidence and provenance](docs/architecture/evidence.md)
- [Command architecture](docs/architecture/commands.md)
- [Dependency and regeneration architecture](docs/architecture/dependencies.md)
- [Provider architecture](docs/architecture/providers.md)
- [Rendering architecture](docs/architecture/rendering.md)
- [Data sources and terms](docs/architecture/data-sources.md)
- [Third-party architecture policy](docs/architecture/third-party.md)

These documents describe current implementation boundaries unless a section explicitly says `planned`.

## Stack

- API: FastAPI, async SQLAlchemy, Alembic, PostgreSQL/PostGIS direction
- Web: React, TypeScript, Vite, TanStack Query, Three.js, React Three Fiber
- Workflow: persisted tasks/events, idempotency, leases, retries and PostgreSQL `SKIP LOCKED` claims
- Geometry/CAD: existing geometry services and a dedicated CAD worker boundary

## Local run with Docker

```bash
cp .env.example .env
# Set a unique AUTH_SECRET in .env
docker compose up --build
```

- Web: http://localhost:5173
- API/OpenAPI: http://localhost:8000/docs

The API container runs `alembic upgrade head` before serving. Application startup never creates tables implicitly. Compose's API health check uses `/ready`, which verifies database connectivity; `/health` is only a liveness endpoint.

### Production configuration

The checked-in `.env.example` is for local Compose only. Before a production deployment, set `APP_ENV=production`, generate a unique `AUTH_SECRET` of at least 32 characters, configure a non-local PostgreSQL `DATABASE_URL` with non-default credentials, and set `CAD_ALLOW_LEGACY_ENGINE=false` while keeping `GEOMETRY_ENGINE=cad_bim`. Configure `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` too when using the Compose-managed database. Production startup fails fast when these required safeguards are not met. Do not commit real secrets or production `.env` files.

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

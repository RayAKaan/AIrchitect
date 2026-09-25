# Nazmak Building Feasibility Platform

Modular-monolith MVP for preliminary commercial/retail building feasibility. The repository includes the phase 0–17 implementation slices; it is **not yet verified as production-ready**. See the master completion audit before relying on any capability.

## Current state

- API: FastAPI + SQLAlchemy async, domain modules and 58 passing unit tests.
- Frontend: React + TypeScript + Vite starter workspace. Dependency installation/build remains unverified.
- Data: PostgreSQL/PostGIS is the intended database. PostgreSQL integration and production migrations remain release gates.
- Safety boundary: structural and regulatory outputs are preliminary; no engineering certification or official regulatory approval is implied. Cost rates must be explicitly sourced and supplied.

## Documentation

- [Master repository audit](docs/completion/MASTER_AUDIT.md)
- [Blueprint traceability matrix](docs/completion/BLUEPRINT_TRACEABILITY_MATRIX.md)
- [Prioritized implementation gaps](docs/completion/IMPLEMENTATION_GAPS.md)
- [Integration defects](docs/completion/INTEGRATION_DEFECTS.md)
- [Verification baseline](docs/completion/VERIFICATION_BASELINE.md)
- [Phase tracker](docs/implementation/PHASE-TRACKER.md)
- [Release checklist](docs/implementation/RELEASE-CHECKLIST.md)

## Local development

1. Copy `.env.example` to `.env` and set a unique `AUTH_SECRET` (at least 32 characters outside local mode).
2. Start dependencies with `docker compose up --build` (Docker required).
3. API docs: `http://localhost:8000/docs`; frontend: `http://localhost:5173`.
4. API tests: `cd apps/api && pytest -q`.
5. Frontend build: `cd apps/web && npm ci && npm run build` (requires a committed lockfile; currently blocked pending dependency resolution).

Local API bootstrap attempts `create_all` for development convenience. Production must use committed Alembic migrations and managed secrets. Authentication remains a starter implementation and requires a production security review.

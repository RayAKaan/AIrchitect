# Master MVP Repository Audit

**Audit date:** 2026-09-25  
**Scope:** Current workspace `nazmak-building-platform`, phase reports 0–17, API test suite, frontend manifests/source, Docker Compose, configuration, and tracker.  
**Audit type:** Static repository inspection plus locally executable API unit suite. This is not a production/security certification.

## Executive finding

The workspace contains a modular FastAPI/SQLAlchemy API, a React/Vite frontend, domain modules for the planned feasibility stages, phase reports, and Compose/CI scaffolding. The API unit suite currently passes (58 tests). However, the application is **not a verified, end-to-end MVP or release-ready**: there is no frontend lockfile or installed dependency tree, frontend build could not be run because `npm install` timed out, database-backed integration and browser E2E were not run, and several domains remain request-driven rather than joined through a durable persisted artifact graph.

The phase tracker had contradictory top-level status rows (for example, early phases marked not started despite their reports and code being present). This audit supersedes those stale summaries: phase files are evidence of implementation slices, not proof of full completion.

## Repository inventory

- `apps/api/app`: FastAPI application, SQLAlchemy models/session, auth dependencies, and domain modules for assumptions, change impact, decisions, estimates, geometry, identity/project schemas, regulatory, requirements, reviews, structure, validation, workflows, and World Model.
- `apps/api/tests`: 58 API unit tests across those domains.
- `apps/web`: React/Vite TypeScript shell, `GeometryViewer.tsx`, CSS, shadcn configuration, package manifest. No `package-lock.json` or installed `node_modules` was present at audit time.
- `docs/implementation`: phase 0–17 reports, tracker, release checklist.
- Root: Docker Compose, Makefile, `.env.example`, CI workflow, release preflight script.

## Verification performed

| Check | Result | Notes |
|---|---|---|
| API unit tests | PASS: 58 | `cd apps/api && pytest -q`; four FastAPI lifecycle deprecation warnings existed before this pass and were removed by lifespan refactor; current run clean. |
| Frontend dependency install | BLOCKED | `npm install --ignore-scripts --no-audit --no-fund` timed out; no lockfile or node_modules resulted. |
| Frontend build / lint / tests | NOT RUN | Dependencies unavailable. |
| PostgreSQL/PostGIS integration | NOT RUN | No verified live database in this audit. |
| Browser E2E | NOT RUN | No browser automation environment verified. |
| Docker Compose/deployment | NOT RUN | Docker CLI unavailable in this environment. |
| Ruff / mypy | NOT RUN | Ruff executable not available in PATH. |

## Confirmed improvements in this completion pass

- Replaced deprecated FastAPI `on_event` startup/shutdown hooks with an async lifespan handler.
- Added fail-closed validation for weak/default `AUTH_SECRET` values outside local mode.
- Reused the configured async SQLAlchemy session factory instead of recreating it for every dependency call.
- Replaced dynamic `__import__('sqlalchemy').JSON` model declarations with direct `JSON` imports.
- Re-ran API tests after these changes: 58 passed.

## Important limitations

1. Local schema bootstrap uses `create_all`; production migration execution remains a release gate.
2. Database-dependent behavior and tenant isolation have not been proven against PostgreSQL.
3. Workflow claiming/recovery remains short of production-grade concurrent worker semantics.
4. Several domain endpoints accept caller-supplied facts/snapshots rather than resolving all dependencies from persisted canonical artifacts.
5. The frontend is a starter workspace shell; not all domain workflows are integrated and the declared shadcn dependencies are not equivalent to complete primitive adoption.
6. Geometry rendering is not yet confirmed as a Three.js/WebGL implementation.
7. Regulatory and structural outputs remain preliminary; no authoritative Saudi rules library or certified engineering analysis is included.
8. The final deliverable assembler still needs a verified cross-domain persisted package and source-hash validation.

## Audit conclusion

Proceed with a staged completion pass, starting with repository/configuration correctness and then persistence/version integrity, workflow orchestration, domain artifact integration, frontend workflow coverage, and release testing. Do not advertise production readiness until the blocked checks are executed in a suitable environment.

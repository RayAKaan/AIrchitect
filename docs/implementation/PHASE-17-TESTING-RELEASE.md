# Phase 17 — Testing & Release Readiness (partial)

## Scope
Cross-phase verification, CI/release preflight hygiene, and an honest release-gate record.

## Verification performed in this environment

- API suite: `pytest -q` — **58 passed**, 4 FastAPI `on_event` deprecation warnings.
- Frontend build: `npm run build` — **blocked/fails** because frontend packages are not installed (`Cannot find module 'react'`).
- Dependency installation: `npm install --ignore-scripts --no-audit --no-fund` — timed out in this environment; no lockfile was produced.
- Docker/PostgreSQL/PostGIS integration: not run; Docker/runtime services unavailable in this environment.
- Browser E2E: not run.
- `scripts/release_preflight.py`: repository evidence/hygiene check; not a production certification.

## Delivered in this phase

- Offline release preflight script checking core files and phase reports, and warning on local/generated artifacts.
- Updated CI workflow with explicit API and frontend jobs, deterministic Node major version, and no cache dependency on a missing lockfile.
- Release gate checklist and phase tracker reconciliation.

## Release blockers / open gates

1. Frontend dependency installation and production build must succeed in a network-enabled CI runner; commit a reviewed lockfile and switch CI to `npm ci`.
2. Run PostgreSQL/PostGIS migrations and DB-backed tests; verify tenant isolation and concurrent workflow claims.
3. Run browser E2E across auth → project → geometry → estimate → validation/review → PDF/JSON.
4. Complete security review (secret management, token revocation/session policy, rate limits, CORS, authorization matrix).
5. Validate PDF artifacts and source revision/hash binding; ensure stale outputs cannot be exported as current.
6. Conduct qualified Saudi regulatory, quantity-surveying, and structural review before external customer use.
7. Build and scan production containers; SBOM/license review; backup/restore and deployment rehearsal.

## Release decision

**NOT RELEASE-READY.** API unit tests pass, but frontend build, DB integration, browser E2E, production security, and domain validation remain unverified. No claim of full MVP completion is made.

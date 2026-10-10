# Phase 21 — Production Hardening & MVP Release

**Status:** In progress. A PR is not a release certification.  
**Baseline:** Phase 20 is merged to `main`; its reported final CI run passed.  
**Goal:** Make production misconfiguration fail fast, provide observable readiness, and make the local Compose path accurately configurable without weakening the CAD authority boundary.

## Repository-grounded plan

### P21.1 — Production configuration guardrails
- Reject default/short auth secrets in production.
- Require a non-local PostgreSQL URL with explicit non-default credentials.
- Require the CAD/BIM engine and disable legacy geometry fallback in production.
- Keep `local` and `test` environments usable without production secrets.
- Make Compose pass environment variables through instead of hardcoding `APP_ENV=local`.

### P21.2 — HTTP security and request correlation
- Accept caller-supplied request IDs only when they match a conservative 1–128 character allowlist; otherwise generate a UUID.
- Add baseline API security headers and disable caching of API responses.
- Keep request IDs available in response headers and structured HTTP errors.

### P21.3 — Deployment readiness and configuration
- Add a container health check against the database-aware `/ready` endpoint, not only process liveness.
- Allow Compose database credentials and environment selection to be configured.
- Document a safe local setup and the required production variables.

### P21.4 — Release evidence and CI
- Test valid/invalid production settings, security headers, and request ID sanitization.
- Add this phase report to release preflight.
- Run Ruff, the full API test suite, PostgreSQL migration cycle, frontend checks/build, both Docker builds, Compose smoke tests, and release preflight in GitHub Actions.
- Review the final CI run and fix regressions before declaring the phase complete.

## Implemented in this PR
- Production config now rejects weak/default secrets, local/default database URLs or credentials, and legacy geometry/fallback.
- Compose environment variables are configurable and the API container checks `/ready`.
- API responses carry baseline security headers; unsafe request IDs are replaced.
- Regression tests cover the production guardrails and HTTP response headers.

## Exit criteria
- [ ] All API Ruff/tests pass.
- [ ] PostgreSQL migration upgrade/downgrade/upgrade passes.
- [ ] Frontend lint/tests/build and API/web Docker builds pass.
- [ ] Compose starts, API readiness and public smoke checks pass, and teardown succeeds.
- [ ] Release preflight passes.
- [ ] Review limitations: this is not a penetration test, SBOM/vulnerability scan, browser E2E suite, managed-database/TLS rehearsal, or validation of the native CAD worker toolchain on the target host.

## Operational boundary
Structural calculations remain conceptual, not professional certification. Regulatory results without authoritative applicable rules remain `UNKNOWN`. A passing software pipeline does not make a feasibility package construction-ready.

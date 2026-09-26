# Phase 1 completion report — Foundation + Building Brain

Date: 2026-09-25
Scope: identity/tenancy, projects, project versions, briefs, requirements, assumptions, canonical World Model, provenance, audit, snapshots and semantic comparison.

## Baseline

The pass began from the integrated repository state documented in `ENGINEERING_COMPLETION_REPORT.md`. The source audit is recorded in `docs/implementation/PHASE-1-COMPLIANCE-AUDIT.md`, with every Phase 1 area classified as already correct, partial, incorrect or missing.

Executed pre-change baseline:

- backend: 67 passed;
- Ruff: passed;
- frontend TypeScript/build: passed;
- Alembic SQLite upgrade/current/downgrade: passed;
- PostgreSQL unavailable locally because Docker, `psql` and `pg_isready` are not installed.

## Changes

### Canonical project/version lifecycle

- Projects now carry `current_version_id` and metadata.
- Project creation transactionally creates Project, V1, an empty typed World Model revision, canonical hash and audit events.
- Project versions now have deterministic server-owned numbers, `DRAFT -> COMMITTED -> SUPERSEDED` semantics, optimistic `revision_number`, parent, source, metadata and per-project idempotency key.
- Version creation locks the project row, verifies expected current version/revision, calculates the next number server-side, clones traceable canonical inputs, applies explicit changes, rebuilds the World Model and updates the canonical pointer.
- Idempotent retries return the original version rather than creating V3.
- Committed/superseded version canonical content cannot be mutated through Phase 1 routes.

### Briefs and requirements

- Added a canonical `building_briefs` domain containing raw text, structured extraction, revision, source/reference and SHA-256 content hash.
- Added the `RequirementExtractor` protocol and conservative `DeterministicRequirementExtractor` implementation.
- Extraction now handles numeric/word floor counts, commercial/retail use, Riyadh and selected cities, site area, target GFA, parking arrangement/count, floor height, building height and budget.
- Canonical units are `m`, `m2`, `count` and `SAR`; raw text/value and typed normalized values are both retained.
- Requirements now persist source type/reference, extraction method, value type, confidence, confirmation actor/time, supersession and update time.
- Added version-scoped list, confirm/reject and non-destructive edit/supersede APIs.
- Persisted unresolved contradictions block version commit.

### Assumptions

- Partial briefs remain valid; missing facts remain `null`/unknown and are not represented by fake zeroes or null-valued assumptions.
- The deterministic engine proposes clearly labeled preliminary assumptions for 5 m floor-to-floor height and reinforced-concrete concept where absent.
- Assumption acceptance/rejection/replacement is version-scoped, optimistic, auditable and rebuilds the canonical World Model.
- Impact scope is persisted.

### Typed Building World Model

- Added a single typed `BuildingWorldModel` with site/location, building, levels, spaces, parking, structural grid, properties, requirement/assumption references, per-value provenance, unknowns and consistency issues.
- World Models are rebuilt only from persisted version requirements/assumptions.
- Six floors generate six typed levels; derived height and per-level area retain derivation provenance.
- Positive quantity validation and explicit height-versus-floors consistency reporting are implemented.
- Deterministic sorted canonical JSON hashing is verified on every canonical resolution.
- `resolve_project_version(...)` and `resolve_world_model(...)` are the central interface future phases can call.

### Canonical-state enforcement

- Direct arbitrary client-owned geometry generation now returns `410 CANONICAL_VERSION_REQUIRED` after tenant authorization.
- Legacy project-scoped World Model and assumption writes are disabled.
- Legacy non-versioned brief/change writes are disabled in favor of optimistic version-scoped APIs.
- Project metadata PATCH cannot silently change building type/location; that requires a canonical version change.

### Tenancy, audit and errors

- Central project/version resolution joins authenticated membership and deliberately returns non-disclosing 404 responses across tenants.
- Audit records now identify project and project version.
- Project/version/brief/requirement/assumption/World Model/commit events are recorded with actor and safe metadata.
- Added project audit history API.
- Added request IDs and a standard top-level error envelope for HTTP errors.

## Database changes

Migration `20260925_0002_phase_1_canonical_building_brain.py` adds:

- `building_briefs`;
- project canonical pointer and metadata;
- version revision/source/metadata/idempotency fields and uniqueness;
- requirement typed value/provenance/confirmation/update fields;
- World Model source/metadata;
- project/version audit references;
- canonical-pointer foreign key and deterministic backfill for existing projects.

The migration uses batch-compatible operations for SQLite fallback and standard constraints compatible with PostgreSQL. Upgrade -> downgrade base -> upgrade head was verified from an empty SQLite database. CI now provisions PostGIS/PostgreSQL 16 and runs the same migration cycle before tests; this CI change has not been executed by this local environment.

## API changes

Primary Phase 1 endpoints:

```text
GET/POST /api/v1/projects/{project_id}/versions
GET      /api/v1/projects/{project_id}/versions/compare
GET      /api/v1/projects/{project_id}/versions/{version_id}
POST     /api/v1/projects/{project_id}/versions/{version_id}/brief
GET      /api/v1/projects/{project_id}/versions/{version_id}/requirements
POST     /api/v1/projects/{project_id}/versions/{version_id}/requirements/{id}/confirm
PATCH    /api/v1/projects/{project_id}/versions/{version_id}/requirements/{id}
GET/POST /api/v1/projects/{project_id}/versions/{version_id}/assumptions
PATCH    /api/v1/projects/{project_id}/versions/{version_id}/assumptions/{id}
GET/POST /api/v1/projects/{project_id}/versions/{version_id}/world-model
GET      /api/v1/projects/{project_id}/versions/{version_id}/snapshot
GET      /api/v1/projects/{project_id}/audit-events
```

Version references accept canonical UUIDs or version numbers for compatibility. Version creation requires `Idempotency-Key` and expected current version/revision.

## Frontend changes

Opening a project now enters a Phase 1 Building Brain workspace containing:

- visible version selector/status/revision/hash;
- raw brief analysis;
- requirement cards with provenance/confidence/confirmation;
- assumption cards with provenance, impacts and decisions;
- structured World Model/unknown/provenance view;
- explicit floor-count version change and impact preview;
- semantic version comparison.

The UI does not expose Phase 2 engineering functionality in this workspace.

## Tests and exact results

Final locally executed results:

- backend pytest: **79 passed**;
- backend Ruff: **passed**;
- frontend Vitest: **3 passed in 1 file**;
- frontend TypeScript check: **passed**;
- frontend production build: **passed**, 77 modules, 230.85 kB JS (71.73 kB gzip);
- npm audit: **0 vulnerabilities**;
- Alembic empty DB upgrade -> current -> downgrade base -> upgrade: **passed**, head `20260925_0002`;
- manual HTTP Phase 1 journey: **passed**.

Added backend coverage verifies transactional V1 creation, empty unknown state, deterministic extraction/normalization, provenance, assumptions, World Model levels, optimistic conflicts, non-destructive requirement editing, commit immutability, idempotent V2 creation, semantic comparison, V1 hash preservation, contradiction blocking, tenant non-disclosure, geometry bypass rejection, deterministic hashing and unknown != zero.

Strict `mypy app` was also attempted and remains failing with **136 errors** across legacy and current modules. Most are pre-existing missing annotations/generic parameters, plus several lifecycle typing issues. Mypy is not in CI and is an explicit remaining quality risk; it is not represented as passing.

## Manual Definition-of-Done journey

Executed against a fresh migrated SQLite database and live FastAPI server:

1. Registered a user/organization.
2. Created `Riyadh Retail Center`; V1 and empty canonical World Model were created atomically.
3. Submitted: “Six-floor commercial retail building in Riyadh, approximately 18,000 m² GFA on a 3,000 m² site, basement parking.”
4. Persisted 6 user requirements with provenance.
5. Proposed and then accepted 2 explicit system assumptions: 5 m floor-to-floor and RC frame concept.
6. Confirmed extracted requirements.
7. Built and committed V1 with 6 levels, typed values, unknowns, provenance and hash.
8. Created V2 through an explicit 6 -> 8 floor change.
9. Resolved V2 as 8 floors/8 levels.
10. Re-read V1 as 6 floors and verified its World Model hash was unchanged.
11. Compared V1/V2 and received `building.floor_count: 6 -> 8`.
12. Retrieved 34 traceable audit events.
13. Resolved the authoritative V2 World Model hash: `6c2c1ca6ea7e2719fb31fc28c755d4eb3ead97022c654ceaec1cec49312f478e`.

## PostgreSQL status

**Not locally executed.** Docker, `psql` and `pg_isready` are unavailable. The schema and row-locking code remain PostgreSQL-oriented, and CI now has a PostGIS/PostgreSQL migration gate. Real concurrent version-creation behavior under PostgreSQL must be observed in CI or a PostgreSQL-capable environment before production use.

## Known limitations and remaining Phase 1 risks

- PostgreSQL migration and true simultaneous row-lock contention remain locally unverified.
- Strict mypy is not clean (136 reported errors).
- Authentication is still a starter token implementation; production sessions/revocation are out of scope.
- The deterministic extractor is intentionally conservative and English-focused; it is not general NLU.
- Requirement confirmation is per-record; a bulk-confirm endpoint is not yet present.
- The UI has unit tests for its canonical view model but no browser automation.
- Existing legacy downstream modules remain in the repository for later phases; unsafe direct mutation paths are disabled, but later phases must refactor their consumers onto `resolve_world_model`.
- Project names are not unique within an organization; duplicate names are allowed and identified by UUID.
- Authoritative regulation, engineering certification and market-rate claims remain outside Phase 1.

## Phase 1 gates

| Gate | Verification |
|---|---|
| One canonical versioned building representation | PASS — project pointer -> version -> hash-verified World Model revision. |
| Partial briefs and unknown != zero | PASS. |
| Requirements distinct from assumptions | PASS — separate tables, states and provenance. |
| Historical V1 survives V2 | PASS — V1 remained 6 floors with unchanged hash after V2 became 8. |
| Deterministic version numbering | PASS — server calculates sequential number under row lock. |
| Optimistic concurrency | PASS in API tests; true PostgreSQL contention pending. |
| Requirement provenance retained | PASS. |
| Canonical deterministic hash | PASS. |
| Snapshot and semantic comparison | PASS. |
| Tenant isolation | PASS in API integration test with non-disclosing 404. |
| Audit history | PASS. |
| Client cannot inject canonical geometry | PASS — unsafe route returns 410. |
| Phase 2 can resolve authoritative state | PASS — `resolve_project_version` + `resolve_world_model` return exact version/hash-verified state. |
| PostgreSQL runtime verification | PENDING external environment/CI execution. |
| Browser E2E | PENDING. |

## Commands

```bash
cd apps/api
pip install -e '.[dev]'
pytest -q
ruff check .
DATABASE_URL=sqlite+aiosqlite:////tmp/phase1.db alembic upgrade head

cd ../web
npm ci
npm run lint
npm test
npm run build
npm audit --omit=dev --audit-level=high
```

Phase 1 is complete as a tested canonical MVP foundation in the available environment, but **production readiness is not claimed**. PostgreSQL concurrency and browser E2E remain explicit release gates.

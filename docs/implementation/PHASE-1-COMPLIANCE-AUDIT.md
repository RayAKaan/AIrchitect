# Phase 1 compliance audit — pre-change baseline

Date: 2026-09-25
Source reviewed: repository code at the start of the Phase 1 pass (documentation was not treated as authoritative).

## Baseline verification

- `pytest -q`: 67 passed.
- `ruff check .`: passed.
- frontend TypeScript and build: passed.
- Alembic upgrade/current/downgrade: passed on SQLite.
- PostgreSQL: unavailable in the execution environment (Docker is not installed).

## Classification

| Specification area | Baseline classification | Source finding |
|---|---|---|
| Identity and organization membership | PARTIALLY IMPLEMENTED | Authentication and membership checks existed, but reusable project/version tenant resolution did not. |
| Project canonical pointer and metadata | MISSING | `Project.version` was a mutable integer; no `current_version_id` or project metadata existed. |
| Transactional project + V1 + initial World Model | PARTIALLY IMPLEMENTED | Project and V1 were created together, but no empty canonical World Model or current-version pointer was created. |
| Deterministic server-owned version numbers | PARTIALLY IMPLEMENTED | Change route incremented `Project.version`; no row lock, idempotency, or dedicated creation service. |
| Version lifecycle/immutability | PARTIALLY IMPLEMENTED | New versions and historical World Models existed, but lifecycle semantics and mutation guards were ambiguous. |
| Optimistic concurrency | PARTIALLY IMPLEMENTED | Legacy World Model mutation checked an expected project integer; Phase 1 mutations had no uniform revision token. |
| Canonical brief object | MISSING | Raw brief was used transiently and only its hash/source fragments were retained. |
| Partial brief support | INCORRECT | Critical absent values generated null-valued assumption records; no typed canonical partial brief existed. |
| Requirement persistence | PARTIALLY IMPLEMENTED | Records existed, but raw value, typed value, source fields, extraction method, confirmation actor/time, and update time were incomplete. |
| Controlled categories/states | PARTIALLY IMPLEMENTED | Categories and statuses were narrower and inconsistently cased. |
| Extractor provider interface | MISSING | Regex extraction was a function coupled to API schemas. |
| Unit normalization/type safety | PARTIALLY IMPLEMENTED | Numeric extraction existed; canonical units and raw/normalized values were not modeled consistently. |
| Location/use/site/parking extraction | PARTIALLY IMPLEMENTED | Floors/GFA/budget/parking count worked; location, building use, site area, and parking arrangement did not. |
| Contradiction detection | PARTIALLY IMPLEMENTED | Brief-local duplicate detection existed; persisted active-version contradiction/supersession handling did not. |
| Requirement confirmation/edit/reject | MISSING | No version-scoped requirement mutation API. |
| Assumption domain | PARTIALLY IMPLEMENTED | Persistence/transitions existed at project scope, but canonical version resolution, optimistic concurrency, and World Model rebuild were absent. |
| Useful system assumptions | INCORRECT | Missing facts became `value: null` assumptions instead of remaining unknown; no explicit preliminary defaults were proposed. |
| Typed Building World Model | PARTIALLY IMPLEMENTED | A Pydantic model existed, but the lifecycle pipeline wrote an incompatible ad-hoc dictionary shape. |
| Unknown versus zero | PARTIALLY IMPLEMENTED | Ad-hoc model used `None`, while typed canonical validation/resolution was not unified. |
| Cross-field World Model validation | MISSING | No deterministic building height/floor-height inconsistency reporting. |
| Deterministic model hash | ALREADY CORRECT | Canonical sorted JSON SHA-256 was used by the lifecycle service. |
| Central canonical resolution service | MISSING | Routes and downstream services issued independent `select` queries. |
| Snapshot | PARTIALLY IMPLEMENTED | Snapshot existed by version number and included downstream artifacts, but lacked canonical brief and a stable version-ID contract. |
| Semantic version comparison | MISSING | No World Model semantic diff API. |
| Audit events | PARTIALLY IMPLEMENTED | Audit table/events existed, but lacked project/version columns, query API, and granular Phase 1 mutation events. |
| Tenant non-disclosure | PARTIALLY IMPLEMENTED | Most routes checked membership after project load; behavior was not comprehensively integration-tested. |
| Idempotent version creation | MISSING | No version creation endpoint or idempotency key. |
| Standard error envelope | MISSING | Routes returned heterogeneous FastAPI `detail` payloads. |
| Phase 1 frontend journey | MISSING | Project list and persisted 3D viewer existed; brief/requirements/assumptions/World Model/version comparison UI did not. |
| Migration coverage | PARTIALLY IMPLEMENTED | A complete explicit initial migration existed; Phase 1 strengthening fields/tables required a new migration. |
| Phase 1 test matrix | MISSING | Deterministic engines and integrated downstream pipeline were tested, but Phase 1 API lifecycle/concurrency/tenant/provenance/comparison coverage was absent. |

## Reusable components

The existing identity, membership, project, `ProjectVersion`, `RequirementRecord`, `AssumptionRecord`, `WorldModelRevision`, audit, canonical hashing helper, deterministic regex rules, Alembic setup, and lifecycle snapshot/change concepts are retained and strengthened. No parallel project architecture is introduced.

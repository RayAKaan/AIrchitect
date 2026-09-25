# Phase 10 — Quantity Takeoff & Cost Estimation (partial)

## Delivered
- Typed quantity inputs with units, provenance/source strings, and bounded nonnegative values.
- User-supplied SAR rate bands (`low <= base <= high`) with source and rate-schedule version.
- Deterministic line-item calculations and low/base/high subtotals.
- Optional percentage contingency applied consistently to each scenario.
- Stable estimate identity hashing the full request, including geometry artifact ID/hash and source revision.
- Authenticated, organization-scoped `POST /api/v1/estimates/calculate` endpoint.
- Explicit preliminary-estimate caveats; no market-rate defaults or contractor/approval claims.
- Unit tests for arithmetic, determinism, rate ordering, unknown quantity references, and geometry-hash identity.

## API outline
`POST /api/v1/estimates/calculate`

Request includes `project_id`, `source_revision`, `geometry_artifact_id`, `geometry_sha256`, `quantities[]`, `lines[]`, and optional `contingency_pct`. Each estimate line references a supplied quantity code and a sourced, versioned SAR rate band.

## Verification
- `pytest -q`: 31 passed.
- Four existing FastAPI lifecycle deprecation warnings.

## Known gaps / exit gates
- Quantity records are accepted as sourced inputs; they are not yet automatically extracted from persisted geometry artifacts or independently reconciled against artifact contents.
- Estimates are calculated synchronously and returned; estimate/rate schedules are not persisted, immutable database records yet.
- No rate schedule administration/import, regional/escalation/tax modeling, scope completeness analysis, or calibrated Saudi market dataset.
- No stale propagation when geometry or rate schedules change; source revision/hash are recorded in the deterministic estimate identity only.
- No PostgreSQL endpoint integration, tenant-isolation integration, frontend estimate UI, or independent QS validation.

This phase is partial and is not a QS-certified estimate, tender, quotation, or construction budget.

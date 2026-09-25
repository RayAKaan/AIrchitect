# Phase 11 — Structural Workflow (partial)

## Delivered
- Added a typed, authenticated, organization-scoped `POST /api/v1/structure/concept` endpoint.
- Added deterministic conceptual framing-grid generation from supplied footprint dimensions and preferred maximum bay spacing.
- Carries project ID, geometry artifact ID/hash, and source revision as provenance.
- Reports indicative grid/beam counts and explicit input-completeness flags; missing imposed load is never silently defaulted.
- Explicitly marks the output `concept_only` and structural capacity, code compliance, and foundation design as unchecked.
- Added tests for determinism, bounds, provenance, missing/user-supplied load, invalid inputs, and non-approval semantics.

## Verification
- `pytest -q`: **37 passed**, 4 existing FastAPI `on_event` deprecation warnings.

## Known limitations / remaining gates
- No persistent structural concept/version records or audit history.
- Geometry hash is carried through but not independently fetched or verified against persisted geometry.
- No load combinations, member sizing, material design, lateral stability, wind/seismic analysis, foundation sizing, or code checks.
- No engineering review/approval workflow, licensed-engineer sign-off, or frontend integration.
- Conceptual grid counts are indicative only and must not be used for construction, permitting, or procurement.
- PostgreSQL-backed integration and production deployment were not verified in this environment.

## Status
Partial; not production-ready and not a substitute for licensed structural engineering.

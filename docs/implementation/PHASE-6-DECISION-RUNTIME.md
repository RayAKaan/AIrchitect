# Phase 6 — Decision Runtime

## Implemented
- Typed request/response contracts with unique allowed-option validation.
- Provider abstraction and deterministic local provider (caller-ordered first option; explicitly not a ranking).
- Fixture-backed benchmark provider that fails closed when no valid fixture exists.
- Jev adapter boundary that fails closed until a documented provider contract and credentials are configured.
- Output validation rejects choices outside the caller's allowed options.
- Authenticated `POST /api/v1/decisions/evaluate` endpoint, selected by `DECISION_PROVIDER`.

## Safety and limitations
- No provider can mutate canonical state: endpoint returns a decision only.
- Deterministic behavior is a fallback policy, not domain reasoning or engineering advice.
- Jev live integration is not implemented; no undocumented fields or endpoints are assumed.
- Decision audit persistence, provider timeout/circuit-breaker policy, and per-decision fallback eligibility remain follow-up work.

## Verification
Run from `apps/api`: `pytest -q`. Tests cover deterministic policy, benchmark fixture behavior, Jev fail-closed behavior, and rejection of invalid provider options. Database is not required for provider unit tests; endpoint auth depends on the existing app auth/database setup.

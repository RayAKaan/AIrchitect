# Phase 12 — Regulatory Engine (partial)

## Delivered
- Configurable, caller-supplied rules with operators: `lte`, `lt`, `gte`, `gt`, `eq`, `in`, `exists`.
- Evidence provenance fields required per rule: source name, reference, and version; optional effective date.
- Deterministic evaluation over supplied facts; missing/incompatible facts return `unknown`, never pass.
- Duplicate rule IDs and missing thresholds are rejected.
- Per-rule results and pass/fail/unknown summary; output is always `preliminary_only` with a non-approval disclaimer.
- Authenticated, project-membership-scoped `POST /api/v1/regulatory/evaluate` endpoint.

## Verification
`pytest -q`: 44 passed. Four pre-existing FastAPI `on_event` deprecation warnings.

## Explicit limitations / remaining gates
- No Saudi code/rule library is bundled or asserted authoritative. Operators must provide reviewed rules and evidence references.
- Rulesets and evaluation results are request-scoped and not persisted as immutable records.
- No geometry/World Model artifact hash verification, stale propagation, official municipality integration, legal interpretation, permit submission, or human authority approval.
- Effective-date strings are provenance only; the engine does not adjudicate applicability by date.
- Production PostgreSQL integration and end-to-end frontend workflow remain unverified.

## Safety boundary
A `pass` means only that the supplied fact satisfies the supplied configured condition. It is not a compliance determination, legal advice, engineering certification, or permit approval.

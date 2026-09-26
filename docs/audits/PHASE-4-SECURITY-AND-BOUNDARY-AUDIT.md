# Phase 4 security and authority audit

## PASS
- Human review remains the highest authority and is mandatory.
- Deterministic engines calculate design/geometry/engineering.
- Decision provider output is bounded and policy-revalidated.
- LLM output is schema-validated, proposed/non-canonical, scoped, hashed, and usage-accounted.
- TypeSafe Jev adapter follows the official System One Choice/Score/Noul HTTP contract.
- Keys are backend-only; provider status does not reveal values.
- Workflow is finite, persisted, idempotent, resumable, cancellable, and failure-aware.
- Tenant checks protect project AI/workflow/evidence/usage/review APIs.
- Assistant is read-only and labels unsupported responses UNGROUNDED.
- Immutable artifacts and stale-state enforcement are preserved.

## NOT RUN
- Live production LLM (no credential).
- Live TypeSafe Jev (no credential).
- PostgreSQL/PostGIS and true concurrent row-lock behavior (runtime unavailable).
- Cross-browser/mobile matrices beyond local Chromium.

## KNOWN LIMITATIONS
- Provider-specific OpenAI compatibility can vary and requires deployment smoke testing.
- Assistant rate limiting is persisted per project, not distributed per-user quota management.
- The evidence graph’s initial links use conservative WORLD_MODEL SUPPORTS relationships; richer domain-edge semantics are future work.
- Frontend bundle remains above Vite’s advisory chunk threshold.

## DEFERRED
Phase 5, Laya, training/fine-tuning/local weights, autonomous loops, certified engineering, BIM authoring, and construction documents.

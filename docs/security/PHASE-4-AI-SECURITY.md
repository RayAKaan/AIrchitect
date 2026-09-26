# Phase 4 AI security and privacy

## Controls
- Authentication and native organization membership guard every project AI, workflow, evidence, usage, decision, and review operation.
- Provider credentials are backend-only settings; status endpoints expose availability, never keys.
- User/model content is untrusted data and cannot alter authorization, canonical state, deterministic constraints, or review.
- Pydantic validates model output; decision options are allowlisted; deterministic policy revalidates recommendations.
- LLM context is minimized, project/version scoped, and token-budgeted. The assistant uses at most 20 evidence nodes.
- The assistant has no mutating tools. It has no SQL, shell, filesystem, database-write, or arbitrary tool interface.
- Per-project assistant calls are rate-limited over a rolling minute using persisted call records.
- Bounded provider timeouts, finite workflow retries, hashes, request IDs, latency/usage, failure classes, and audit events support incident review.

## Threat outcomes
Prompt injection is detected for operator visibility but security does not depend on detection: enforcement remains server-side. Cross-tenant IDs resolve to denial/non-disclosure. Invalid provider options, primitive mismatches, stale artifacts, hard blockers, and unsupported review states fail closed.

## Secrets and logs
Do not log request authorization headers, API keys, or complete sensitive prompts. Environment variables include `LLM_API_KEY` and `JEV_API_KEY`. Browser APIs receive provider name/status and usage only.

## Deployment notes
Rotate credentials and authentication secret through the deployment secret manager. Tune budgets, provider timeouts, and cost rates. PostgreSQL concurrency behavior must be verified in the deployment environment before making concurrency claims.

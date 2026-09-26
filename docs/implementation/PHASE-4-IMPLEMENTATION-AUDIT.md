# Phase 4 Implementation Audit

**Date:** 2026-09-25  
**Status:** completed before Phase 4 code changes

## Existing reusable architecture

- Canonical resolution is implemented by `resolve_project_version(...)` and `resolve_world_model(...)`; these remain mandatory.
- Phase 2/3 provide deterministic design, geometry, quantities, optional sourced cost, structural concept, regulatory evaluation, validation, hashes, staleness, tenant isolation, audits, and a Design workspace.
- `ArtifactVersion` and `ArtifactDependency` are the sole artifact dependency graph.
- Existing `WorkflowRecord` / `WorkflowTaskRecord` already provide persisted workflows, task dependencies, attempts, leases, idempotency keys, cancellation, and generic worker APIs. Phase 4 will evolve these tables/classes rather than duplicate them.
- Existing `DecisionProvider` supports deterministic and benchmark providers; `JevProvider` is intentionally unconfigured. It will be replaced with a verified TypeSafe HTTP adapter and wrapped by a provider-neutral runtime.
- Existing `DecisionRecord` is sparse and will be expanded rather than replaced.
- Existing `EvidenceRecord` is artifact-centric. Phase 4 requires generalized typed evidence nodes/links while retaining existing evidence records.
- Native auth and `require_membership(...)` provide organization isolation. Phase 4 APIs must scope every workflow, context, decision, evidence and review through these interfaces.

## Safety findings

- The legacy generic workflow API accepts caller-defined task graphs. It is retained for compatibility but is not used as the authoritative AIrchitect feasibility workflow.
- The old lifecycle pipeline predates Phase 2/3 and duplicates design/geometry generation. Phase 4 will not call it.
- LLM output must remain a proposed record; no provider receives mutation/database/shell tools.
- Jev is advisory only. The deterministic policy gate owns final disposition and cannot permit hard blockers or invalid alternatives.
- The live TypeSafe contract was checked against official docs: `POST https://api.typesafe.ai/v1/systemone` with Bearer auth, `state`, `model`, and typed Choice/Score/Noul questions; response contains typed `answers`, actual model, usage, and request ID where supplied.

## Implementation decisions

- Extend existing workflow/decision models and add LLM calls, evidence nodes/links, review records, and decision evaluations in Alembic revision `20260925_0005`.
- Add provider-neutral LLM schemas/providers with deterministic local operation and an OpenAI-compatible server-side HTTP provider. No production provider is called without explicit configuration.
- Add a real TypeSafe Jev HTTP provider using the documented System One contract; live calls are opt-in and never faked.
- Add `DecisionRuntime` and `DecisionPolicyEngine` with deterministic fallback, confidence routing, schema validation, persistence, usage accounting, and hard-gate enforcement.
- Implement a bounded synchronous persisted state machine that composes existing Phase 2/3 services and pauses at human review. No agent loop or mandatory Temporal dependency.
- Build deterministic change-impact, evidence graph, assistant context/explanation, usage, review, resume/cancel, and version comparison endpoints.
- Extend the existing workspace with AI/Workflow, Evidence, and Review views.

## Verification plan

Run all Phase 1–3 regressions plus focused LLM, Jev, policy, workflow, impact, evidence, review, assistant, injection, usage, idempotency, V1/V2, and tenant tests; SQLite migration and legacy cycles; frontend tests/typecheck/build; real Chromium E2E; OpenAPI generation; dependency audit; and a post-implementation safety audit. Live LLM, live Jev, PostgreSQL, and PostgreSQL concurrency remain NOT RUN unless credentials/infrastructure are actually available.

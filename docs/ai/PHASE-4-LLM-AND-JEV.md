# Phase 4 LLM and Jev contracts

## LLMProvider
`LLMProvider.structured` is provider-neutral and requires a Pydantic output schema. The deterministic adapter validates output produced by deterministic AIrchitect extraction/narration; it does not masquerade as a live model. The production adapter sends minimized context and a JSON schema to an OpenAI-compatible server.

Persisted call metadata includes provider, actual model/version, prompt/schema versions, request ID, input/context/output hashes, status, latency, token counts, estimated/actual cost, and provider metadata. Failed calls are also recorded. Context is budget-limited.

## TypeSafe Jev
The server-side adapter calls `POST {base}/v1/systemone` with Bearer authentication and documented `state`, `model`, and named `questions`. It supports:
- Choice for finite alternative/routing selection;
- Score for an explicitly aligned ordered rubric;
- Noul for an explicit two-option yes/no mapping.

Responses validate primitive type and allowed output. Actual model, request ID, probabilities, confidence, and token usage are retained. API keys never enter browser payloads or logs.

## Failure behavior
Jev is optional. Disabled/unconfigured explicit Jev mode fails closed. `auto` may use deterministic fallback and records the provider error class without credentials. LLM errors do not become canonical values.

## Prompt-injection boundary
User text is labeled untrusted data. System instructions forbid obeying embedded instructions, and authorization/scope, deterministic validation, canonical commits, and review are enforced outside the model. No SQL, shell, filesystem, arbitrary write, or arbitrary tool surface is exposed.

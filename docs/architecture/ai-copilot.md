# AI Copilot execution boundary

AIrchitect's Copilot is an intent and proposal layer, not a second source of truth.

## Execution flow

1. The server resolves one canonical project version and World Model revision.
2. The Copilot builds a bounded, deterministically hashed context envelope.
3. The LLM returns an `AIProposalDraft`; it cannot mutate canonical state.
4. The server adds canonical identity and validates evidence citations.
5. Proposed commands are compiled through the same command registry used by deterministic editing.
6. The deterministic plan preview computes execution order, impact groups, and fingerprint.
7. A short-lived HMAC approval token binds the proposal, plan fingerprint, project/version, and World Model revision.
8. The read-only acceptance endpoint rechecks those bindings immediately before commit.
9. The commit boundary re-resolves canonical state, rejects stale revisions, executes the validated command batch, invalidates affected artifacts, enqueues regeneration, and persists one World Model revision.

## Safety invariants

- LLM output cannot directly mutate canonical state.
- AI proposals always require human confirmation.
- Evidence citations must belong to the server-supplied evidence set.
- Unsupported commands are rejected by the same registry used by deterministic execution.
- Approval tokens are short-lived and cryptographically bound to the proposal and plan.
- A proposal computed against an old World Model revision cannot be committed.
- Plan preview and commit use the same canonical command semantics.
- Canonical persistence remains the authoritative source of truth.

## API surface

- `POST /api/v1/projects/{project_id}/ai/copilot/preview`
- `POST /api/v1/projects/{project_id}/ai/copilot/plan-preview`
- `POST /api/v1/projects/{project_id}/ai/copilot/approval-token`
- `POST /api/v1/projects/{project_id}/ai/copilot/acceptance`
- `POST /api/v1/projects/{project_id}/ai/copilot/commit`

The acceptance endpoint is read-only. The commit endpoint is the only Copilot endpoint in this slice that mutates canonical state, and it requires an authenticated user plus a valid approval token.

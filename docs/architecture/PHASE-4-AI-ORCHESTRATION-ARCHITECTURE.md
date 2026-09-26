# Phase 4 AI-assisted feasibility orchestration architecture

## Authority order
1. Human reviewer
2. Deterministic AIrchitect domain engines
3. TypeSafe Jev bounded decision layer
4. LLM interpretation and explanation

No lower layer can override a higher layer. Confidence changes routing only.

## Flow
`Brief → structured proposal → human-confirmed canonical World Model → bounded routing → deterministic design/geometry/engineering → evidence → mandatory review`

The workflow is a finite persisted state machine (`FEASIBILITY_V1`), not an agent loop. It composes the existing World Model, computational-design engine, Geometry IR, quantity, cost, structural concept, regulatory, and validation services. Workflow and step inputs/outputs are hashed. Every terminal feasibility package waits for `HUMAN_REVIEW_GATE`.

## Boundaries
LLMs extract, clarify, explain, and narrate. They never calculate engineering, authorize, certify, approve, directly mutate canonical state, or bypass tenant scope. Jev recommends among caller-bounded options. `DecisionPolicyEngine` rejects invalid routes and overrides recommendations when deterministic blockers exist.

## Persistence
Migration `20260925_0005` evolves existing workflow, decision, and review entities and adds LLM usage, typed evidence nodes/links, and decision evaluation storage. Existing artifacts remain immutable; stale state is preserved.

## Runtime modes
Deterministic is the credential-free default. `auto` tries Jev only when explicitly enabled with a key and records fallback. Production LLM uses a configurable OpenAI-compatible structured-output endpoint. Credentials are backend settings only.

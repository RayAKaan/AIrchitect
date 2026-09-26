# Phase 4 implementation guide

## Configuration
- `LLM_PROVIDER=deterministic|openai-compatible`
- `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`, timeout/token/cost settings
- `DECISION_PROVIDER=deterministic|jev|auto`
- `JEV_ENABLED`, `JEV_API_KEY`, `JEV_MODEL`, `JEV_BASE_URL`, timeout/token/cost settings
- `ASSISTANT_RATE_LIMIT_PER_MINUTE`

Deterministic mode requires no production credentials.

## Primary APIs
- `POST /projects/{id}/ai/intake`
- `POST /projects/{id}/assistant`; `GET /projects/{id}/ai/usage`
- `GET /ai/providers/status`
- `POST /projects/{id}/workflows/feasibility`
- `GET /projects/{id}/workflows`; `GET|POST /workflows/{id}[/resume|/cancel]`
- `GET /projects/{id}/versions/{version}/change-impact`
- `GET /projects/{id}/evidence`; node and graph views
- `POST /decisions/evaluate`
- `POST /reviews`; `GET /reviews/{project_id}`

## Migrations
Run `alembic upgrade head`. Revision 0005 is batch-safe on SQLite and creates the Phase 4 metadata/indexes. Validate with upgrade, downgrade to 0004, re-upgrade, and `alembic check`.

## UI
The design workspace includes AI / Workflow, Evidence, and Review tabs with provider/usage status, timeline, change impact, evidence IDs, grounded assistant, stale state, and three explicit review actions.

## Testing
Credential-free CI uses deterministic providers. Live tests must be opt-in and must not run unless credentials are present. Never substitute fabricated live responses; HTTP contract unit tests use clearly identified mocks.

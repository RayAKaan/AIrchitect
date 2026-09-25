# Phase 15 — Review & Deliverables (partial)

## Delivered
- Persisted review decisions with reviewer identity, rationale, artifact/version and source hash.
- Organization membership checks; review creation limited to owner/admin/member, listing available to project members.
- Audit event for review creation.
- JSON feasibility deliverable endpoint storing a payload record.
- PDF feasibility deliverable endpoint with project/artifact/version/hash, validation/currentness labels, summary, supplied sections, and explicit preliminary-only disclaimer.
- Allowlisted review decisions and validation-state enum; rationale length validation.
- Four schema tests; complete API suite: 58 passed.

## API
- `POST /api/v1/reviews`
- `GET /api/v1/reviews/{project_id}`
- `POST /api/v1/reviews/deliverables/json`
- `POST /api/v1/reviews/deliverables/pdf`

## Limitations / open gates
- Deliverable records are stored, but immutable storage, content-addressed integrity, and retrieval/version history are not implemented.
- Source hash is caller-supplied and not independently recomputed against canonical artifacts.
- Review decision does not assert regulatory approval or engineering certification; no multi-review quorum or separation-of-duties policy yet.
- PDF is a basic text-oriented report; branding, pagination polish, tables, charts, and browser download integration need work.
- JSON/PDF generation currently accepts caller-supplied sections rather than assembling verified outputs across all domains.
- PostgreSQL integration, frontend build, and browser end-to-end verification remain outstanding.
- Four existing FastAPI lifecycle deprecation warnings remain.

## Safety statement
A recorded `approved_for_feasibility_use` decision is an internal human review status only. It is not a permit, statutory approval, engineering certification, or authorization to construct. Deliverables remain preliminary and source-hash verification is not independently enforced in this phase.

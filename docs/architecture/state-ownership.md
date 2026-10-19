# State Ownership

**Status:** current-state contract plus explicit future boundaries.

The purpose of this document is to prevent duplicate sources of truth while the professional workspace is built incrementally.

## Ownership matrix

| Concern | Current authoritative owner | UI role | Planned evolution |
|---|---|---|---|
| Identity/session | FastAPI auth + session token | collect credentials, display session | move auth concerns into `app/auth` without changing backend authority |
| Organization/project | backend project domain + DB | browse/create/open | dedicated Projects feature |
| Project version | `ProjectVersion` | select/display | explicit version context in workspace |
| Requirements | requirement domain + DB | display/propose/confirm | Brief workspace with explicit proposal/confirmation states |
| Assumptions | assumption domain + DB | inspect/approve | assumption inspector and provenance |
| Canonical World Model | `WorldModelRevision` | project/edit projection | unified command bus and richer semantic model |
| Artifact lineage | `ArtifactVersion` + `ArtifactDependency` | display status/impact | dependency-aware regeneration |
| Change impact | Phase 27 change-impact services | preview/display | command impact preview before commit |
| Durable work | persisted task/workflow records | progress/status/cancel | unified regeneration/task UX |
| Site geometry | **not yet implemented as a canonical Site World Model** | current UI may display project data | Site World Model becomes authoritative |
| Building geometry | existing geometry/design artifacts | current workspace projection | semantic building model becomes source of truth |
| Drawings | derived artifact systems | future editor | drawing compiler output; annotations separate |
| Boards | partial/current workspace concepts | future editor | board spec is presentation state, not model state |
| Map | future adapter | projection only | MapLibre adapter; never calculation authority |
| 3D renderer | future adapter | projection only | renderer consumes semantic/derived model |
| AI output | AI services/proposals | candidate UI state | structured proposal; never direct canonical mutation |

## State classes

### Canonical state

State that determines the project itself. Examples are project versions, requirements after confirmation, assumptions after acceptance, World Model revisions, and future Site/Building semantic entities.

Canonical state is persisted, versioned, validated, hashed where required, and owned by backend domain services.

### Derived state

State generated from canonical revisions: diagrams, meshes, drawings, analysis results, quantities, costs, exports and presentation artifacts. Derived state carries source revision/hash and dependency lineage and may become stale.

### Ephemeral UI state

Selection, active tool, viewport camera, open panels, hover state, temporary drawing previews, unsaved form text and local UI preferences. This state must never silently become canonical state.

### Proposal state

AI or deterministic generators may create candidate requirements, concepts, edits or recommendations. A proposal is not canonical until it passes schema/domain validation and an explicit commit path.

## Frontend rules

- TanStack Query owns server-cache concerns, not canonical business state.
- Zustand is appropriate for cross-feature UI state such as selection/tool/viewport/panels; it must not become a second backend database.
- Feature components call domain adapters/commands rather than mutating canonical objects directly.
- Map and renderer adapters receive canonical/derived snapshots and emit interaction intents.
- Cross-feature imports should flow through shared infrastructure or stable contracts, not private implementation details.

## Revision rule

A user-visible edit that changes canonical state must create a new revision. Undo/restore is also a new revision; history is never rewritten.

## Conflict rule

A command must identify its base revision/hash. If the canonical state has changed since that base, the command must fail or enter an explicit rebase/conflict path. Silent last-write-wins is not acceptable for professional model editing.

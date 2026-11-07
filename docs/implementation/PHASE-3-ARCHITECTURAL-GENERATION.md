# Phase 3 — Architectural Generation: Programme to Editable Building

**Scope:** The six-deliverable architectural-generation milestone in the product roadmap. This is distinct from the legacy MVP tracker row named “Phase 3 — World Model” and from historical Phase 24/25 labels.

**Status:** Phase 3 implementation PRs 1–6 are merged (#356–#361). The milestone remains in progress because the complete brief-to-editable-building acceptance journey, full architectural element coverage, native CAD-host validation and six-family benchmark evidence are not yet complete. Merged implementation foundations must not be confused with completion of the acceptance gates.

## Objective

Turn a reviewed architectural programme and selected concept into an actual, editable, geometrically valid building model. The target vertical slice is:

Brief → Requirements → Canonical World Model → Programme → Planning Envelope → Selected Concept → Spatial Layout → Topology/Circulation → Architectural Elements → Parametric Geometry → Validated Model

The existing semantic World Model, designer editing/history, command runtime, artifact dependency graph, geometry worker and rendering stack are foundations to reuse—not parallel systems to duplicate.

## Non-negotiable invariants

- The persisted, hash-verified World Model and semantic graph remain the sole canonical building state.
- Generated layouts, element sets, meshes, CAD files and views are versioned derived artifacts. They never silently become canonical state.
- Every generated artifact records the exact World Model, site revision, programme, envelope, selected alternative, engine and configuration lineage used to produce it.
- Stable semantic IDs survive value edits; relationships must reference existing elements.
- All dimensions use explicit metric units and a declared local coordinate system.
- Missing dimensions, site evidence, circulation, access, egress or regulatory facts remain explicit UNKNOWN, UNDERCONSTRAINED or REVIEW_REQUIRED states.
- AI may propose intent. Deterministic domain validation and explicit human commit remain authoritative.
- Undo/redo append new revision/history events; committed historical versions are immutable.
- Reuse the existing ArtifactVersion / ArtifactDependency graph and persisted regeneration runtime. Do not create a parallel dependency graph.
- Open-source CAD/BIM and geometry dependencies must permit free commercial use; retain the existing licence-policy gate and document any legal clearance still outstanding.

## Six PR delivery plan

### PR 1 — Programme-to-spatial layout

- Resolve the current canonical programme, planning envelope, selected design alternative and exact World Model/site revision.
- Compile stable, deterministic floor plates and room polygons with programme IDs, area bounds, floor placement and provenance.
- Reconcile room areas against selected concept GFA and ensure every generated polygon is inside the selected footprint and buildable envelope.
- Persist a versioned spatial_layout artifact with dependencies on programme, envelope and selected alternative.
- Reject stale source lineage, unselected/stale concepts, missing floor count, disconnected buildable envelopes and infeasible footprints.
- Mount and test the programme, envelope and concept routes needed by the vertical slice.

### PR 2 — Spatial topology and circulation

- Build a typed spatial adjacency graph from layout polygons and programme relationships.
- Add room connectivity, shared-boundary validation, circulation zones, access relationships and vertical connectivity candidates.
- Detect disconnected spaces, non-manifold boundaries, unreachable required spaces and unresolved circulation.
- Keep door locations, accessibility, fire egress and code-specific dimensions unknown until their authoritative inputs and rule packs exist.
- Persist topology as a derived artifact bound to the exact layout hash.

### PR 3 — Architectural element generation

- Generate canonical semantic Wall, Partition, Door, Window, Slab, Stair, Ramp and Roof elements from reviewed spatial topology.
- Preserve host/containment relationships, stable IDs, level placement, dimensions, units and source provenance.
- Validate wall joins, opening containment/overlap, slab boundaries, stair/ramp continuity and component ownership.
- Do not generate openings or vertical elements when their placement/geometry is underconstrained.
- Commit generated elements through the existing semantic revision/command lifecycle, with preview, audit and undo/redo.

### PR 4 — Parametric building geometry

- Extend the existing CAD worker to compile the canonical semantic elements—not only massing footprints—into real parametric B-rep solids.
- Support wall openings, slabs, roofs, stairs and ramps with deterministic feature dependencies.
- Validate shape validity, closure, intersections, tolerances and source hashes in the native geometry kernel.
- Produce hash-bound native and exchange artifacts only when the corresponding geometry is complete and validated.
- Keep the API interpreter isolated from native CAD dependencies and preserve bounded worker execution.

### PR 5 — Constraint solving and dependency-aware regeneration

- Add deterministic hard-constraint evaluation for geometry, area, site/envelope fit, adjacency, circulation and element integrity.
- Distinguish hard constraints from preferences and multi-objective trade-offs; never hide failed/unknown constraints in a weighted score.
- Generate reproducible alternatives and explain the changes required to satisfy constraints.
- Connect canonical commands to the existing artifact dependency graph and durable regeneration queue.
- Protect locked elements, reject stale jobs, use idempotency, and atomically persist revisions, audit events, invalidation and regeneration state.

### PR 6 — End-to-end validation, rendering and benchmarks

- Complete the shared 2D/3D/plan/section/elevation scene contract and stable semantic selection across views.
- Support interactive inspection and editing without making renderer geometry authoritative.
- Connect deterministic natural-language intent preview to the supported command subset; ambiguous intent must ask for clarification and preview must never commit.
- Add full browser acceptance from brief through editable building, including undo/redo, regeneration and stale-state behavior.
- Benchmark residential, commercial, office, mixed-use and institutional cases; publish per-case success, area error, topology/constraint findings, geometry validity, latency and limitations.
- Record full CI, licence-policy and release-preflight evidence. Native CAD-host and legal release gates remain explicitly separate if not executed.

## Acceptance gates

1. A supported project can complete the full vertical slice from reviewed brief/programme to a persisted editable semantic building.
2. Room polygons and generated architectural elements have stable IDs, typed properties, valid relationships, source provenance and exact source hashes.
3. Programme area and generated floor area reconcile within 0.02 m² or the artifact is rejected/review-required with a precise reason.
4. No generated geometry extends outside the selected buildable footprint/envelope.
5. Required adjacency and connectivity results are explicit; unresolved circulation/egress is never reported as passed.
6. Parametric CAD solids are generated and kernel-validated from canonical semantic elements, not client-authored or renderer-derived geometry.
7. Edits are revision-checked, audited, undoable/redoable and trigger correct downstream invalidation/regeneration.
8. Plan/3D selections resolve to the same semantic IDs; stale render artifacts are never shown as current.
9. All six building-type benchmark families are committed fixtures with reproducible outputs and documented failure cases.
10. Full backend, migration, frontend, browser, Docker/Compose, CAD licence-policy and release-preflight CI passes on the final PR heads.

## Existing repository foundation and gaps

| Capability | Existing foundation | Phase 3 integration still required |
|---|---|---|
| Semantic building graph | Phase 24 stable IDs, typed properties, relationships and provenance | Promote generated spaces/elements into the same canonical revision |
| Designer editing | Phase 25 locks, overrides, revision history, undo/redo and intent refresh | Generated element commits, full geometry mutation and regeneration integration |
| Parametric geometry | S10 model types, Shapely derivation and opening-aware walls | Bridge semantic World Model elements to native CAD worker feature generation |
| CAD/BIM worker | OCCT/FreeCAD worker and exchange pipeline | Element-level solids and full building topology, beyond massing extrusions |
| Rendering | Scene contracts, 3D inspection and renderer adapter boundary | Shared plan/section/elevation canvas and canonical selection/editing |
| Commands | S3 preview/commit/history/idempotency/regeneration foundation | Broader supported building commands and end-to-end natural-language flow |
| Dependencies | Persisted artifact graph and regeneration jobs | Ensure every new Phase 3 artifact and mutation participates in atomic invalidation |

The older apps/api/app/domains/design/compiler.py produces a separate prototype ArchitecturalModel using a simple room packer. It is not the authoritative Phase 3 pipeline and must not be treated as a second canonical World Model.

## PR 1 implementation record

- Adds a deterministic, versioned spatial_layout artifact derived from the current programme, envelope and selected alternative.
- Generates stable floor/space IDs, metric floor plates, room polygons, area reconciliation, adjacency results, assumptions and explicit topology unknowns.
- Uses the selected buildable polygon and rejects disconnected envelopes, non-fitting footprints, inconsistent programme areas, mismatched floor counts and exceeded envelope limits.
- Binds the artifact to World Model, programme, envelope, selected alternative and site revision lineage.
- Registers the previously unmounted programme, envelope and concept routers alongside the new spatial-layout API.
- PR 1 deliberately does not claim a circulation network, egress solution, doors, complete architectural components or native B-rep geometry; those are later PR acceptance gates.


## PR 3 implementation record

- Adds deterministic wall and partition candidates from the exact room-boundary geometry, including T-junction noding, shared-boundary deduplication, non-manifold rejection and topology-edge lineage.
- Adds per-storey floor-slab proposals from validated room-polygon unions. Courtyard/void boundaries remain unresolved rather than being silently filled.
- Persists wall/slab proposal artifacts against the exact spatial layout and topology hashes, with stable candidate IDs, source-space lineage, local metric geometry and explicit missing dimensions.
- Adds a review/commit endpoint that forks the immutable committed source version into a draft, requires human-reviewed wall height/thickness or slab thickness, promotes stable IDs into the canonical semantic graph, records provenance/audit history, and uses the existing undo/redo event lifecycle.
- Door/window locations, roof geometry, stairs, ramps, and fire/accessibility facts remain explicit unknowns where the source data does not provide authoritative geometry. PR 3 does not claim those elements are generated.

## PR 2 implementation record

- Adds a deterministic `spatial_topology` artifact derived from the exact current spatial-layout hash.
- Validates semantic space IDs, storeys, polygon geometry and declared-area agreement; detects shared-boundary contacts, overlaps and disconnected per-floor components.
- Records explicit circulation-zone contacts and vertical-core candidates without treating a shared boundary as a traversable doorway.
- Preserves unresolved door placement, accessible routes, fire egress, exit distances, stairs, ramps and lift geometry as review/unknown states.
- Persists topology with exact layout lineage and stale-artifact detection. It is a review graph, not a validated circulation or egress solution.

## PR 4 implementation record

- Compiles reviewed canonical semantic Wall and Slab elements into metric B-rep solids through the isolated CAD worker.
- Preserves semantic IDs, World Model and semantic-model hashes, storey placement, coordinate system and units in worker metadata.
- Validates wall-axis dimensions and slab polygon closure, planarity, voids and declared-area reconciliation before persistence.
- Persists CAD runs, geometry artifacts and validation evidence against exact source lineage, including semantic-model jobs without a design-alternative foreign key.
- Current automatic B-rep coverage is limited to reviewed walls and floor slabs. Wall-opening cuts, roofs, stairs, ramps, native FreeCAD semantic feature generation, host-containment/intersection checks and full feature dependency regeneration remain outstanding.

## PR 5 implementation record

- Adds deterministic hard-constraint evaluation over exact World Model, spatial layout, topology, architectural-element and planning-envelope lineage.
- Validates topology identity, area reconciliation, footprint/envelope fit, maximum footprint/GFA, topology errors, wall axes, slab boundaries/areas and required programme adjacencies.
- Separates hard constraints, preferred adjacency objectives and unresolved circulation/egress evidence. Missing hard dimensions are not treated as passes.
- Persists hash-bound `architectural_constraints` artifacts with exact source dependencies, audit history and idempotent reuse.
- Extends regeneration planning/execution support and targeted invalidation for spatial layout, topology, architectural elements and constraints.
- Outstanding: broader structural/material, vertical-connectivity, opening/host and regulatory evidence; complete command preview/commit and durable regeneration coverage for every geometry mutation; undo/redo and stale-job end-to-end cases.

## PR 6 implementation record

- Extends the canonical scene contract with mesh face-index validation and exact semantic-node-to-mesh/model lineage checks.
- Adds deterministic orthographic plan, front and side projections that reuse the scene mesh and stable semantic IDs, while retaining the interactive 3D canvas.
- Adds selectable orthographic views to the scene workspace. Rendering remains read-only and does not become an authoritative geometry source.
- Fixes the CI-discovered concurrent refresh-token race that could sign a user out during a React Strict Mode session restoration.
- Latest-head CI passed for PR #361, including API, web, browser acceptance, runtime smoke, release preflight and Docker Compose checks.
- Outstanding: complete end-to-end browser acceptance from brief through editable building, full natural-language command flow, professional drawing-sheet/dimension authoring, hidden-line removal, section-plane clipping, broader element mesh coverage and all six benchmark families.

## Merged implementation status and remaining acceptance

All six planned Phase 3 implementation PRs are merged:
- PR #356 — programme-to-spatial layout
- PR #357 — spatial topology and circulation review graph
- PR #358 — reviewable architectural element proposals
- PR #359 — canonical wall/slab B-rep geometry
- PR #360 — hard constraints and regeneration foundation
- PR #361 — shared scene and orthographic views

This is not a Phase 3 completion declaration. The acceptance gates above remain the source of truth. In particular, the project still needs complete semantic element/geometry coverage, the full brief-to-editable-building journey, complete command/regeneration/undo-redo behavior, native CAD-host and legal release evidence where applicable, and reproducible results for all six building-type benchmark families. Keep the milestone status In progress until those gates are evidenced on the final main branch.

# Phase 24 — Semantic Building World Model & Parametric CAD Intent

**Status:** Implementation in progress on `feat/phase-24-semantic-building-world-model`.  
**Base:** `main` after Phase 23 PR #5 was merged (merge commit `1780ccf9fe2424741745c09d1bf4e02b7f45e401`).

## Objective

Make the hash-verified canonical Building World Model semantically inspectable and suitable for deterministic downstream CAD/BIM compilation. A building, site, storeys, spaces, and known facilities must have stable identities, typed properties, explicit relationships, and requirement provenance. Geometry mapping must report missing inputs rather than silently inventing dimensions or claiming a valid solid.

## Repository-grounded findings

- The canonical model stores structured site/building/level/space/parking data and requirement provenance, but has no stable semantic element identity or relationship graph.
- CAD/BIM tooling already exists in an isolated worker; it needs a version-bound semantic mapping contract instead of ad-hoc interpretation.
- The canonical model has floor areas and floor counts in many briefs, but normally lacks a verified footprint width/depth and explicit wall/opening geometry. Area alone is insufficient to uniquely determine a building solid.
- Historical World Model revisions must remain readable, hash-verifiable, and immutable. New derived semantics therefore belong inside the persisted canonical revision payload, while older revisions receive a deterministic read-time projection.

## Work packages

1. **Canonical semantic graph**
   - Add a versioned semantic-model payload to `BuildingWorldModel`.
   - Persist a deterministic graph in every newly created World Model revision before computing its SHA-256 content hash.
   - Include Site, Building, Storey, Space, and ParkingFacility only when supported by canonical facts.
   - Add stable project-scoped IDs, typed property values/units, source provenance, and explicit relationships.
   - Keep unmodelled architectural types (Wall, Slab, Roof, Door, Window) visible as unknown capabilities; never synthesize them.

2. **Semantic-to-CAD/BIM contract**
   - Define versioned mapping metadata to IFC classes and CAD feature intents.
   - Compile deterministic parametric feature specifications from the semantic graph.
   - State required parameters and missing dimensions per intent.
   - Return `UNDERCONSTRAINED` until required dimensions exist; do not fabricate B-rep solids or export claims.

3. **Inspection API**
   - Add tenant-scoped, version-scoped semantic-model and parametric-geometry inspection endpoints.
   - Resolve only the canonical version and verify its existing World Model hash before serving.
   - Preserve backward compatibility for pre-Phase-24 revisions by deterministically projecting their existing payloads.

4. **Verification and regression safety**
   - Test deterministic output, stable identity across value changes, typed properties/provenance, relationships, underconstrained geometry, explicit-dimension readiness, and API integration.
   - Preserve the existing requirements, commit gates, CAD authority, artifact lineage, and feasibility workflow.
   - Record phase scope, limitations, acceptance evidence, and unresolved operational gates.

## Definition of Done

- [ ] Semantic graph is persisted within each newly generated canonical World Model revision and covered by the same canonical content hash.
- [ ] Semantic IDs are deterministic and stable across value edits for the same project-level element identity.
- [ ] Properties are typed and retain source provenance where available.
- [ ] Relationships validate to existing element IDs and remain deterministic.
- [ ] Missing architectural entities are represented as unknown capabilities, not invented elements.
- [ ] Semantic-to-CAD/IFC mapping is versioned and exposes required parameters.
- [ ] Parametric compilation is deterministic and reports missing inputs; no underconstrained model is labelled ready.
- [ ] API access is tenant- and version-scoped and verifies the canonical hash.
- [ ] Backend Ruff/pytest, PostgreSQL migration cycle, frontend lint/tests/build, Docker builds, Compose health/smoke, licence policy, benchmark, and release preflight pass.
- [ ] CI evidence is recorded in this plan, the completion report, and phase tracker.

## Explicit boundaries

This phase creates a semantic graph and deterministic parametric feature-intent contract. It does **not** claim that a B-rep, STEP, IFC, or GLB has been generated or validated merely because a feature intent exists. Native CAD worker execution, export interoperability, actual architectural component modelling/editing, engineering approval, and regulatory certification remain separate acceptance gates. Geometry must remain `UNDERCONSTRAINED` when dimensions or relationships are missing.

# S2 — Brief → Requirements → Program → Envelope → Concepts

**Stage:** S2  
**Status:** Backend computational contract implemented; UI workflow remains  
**Scope:** Turn a natural-language architectural brief plus the canonical Site World Model into a traceable, validated program, deterministic buildable envelope, and materially different concept alternatives.

## Product contract

AIrchitect remains the authority for structure, constraints, provenance, validation, geometry, and persistence. An AI model may interpret or propose content, but it cannot silently commit requirements, planning rules, geometry, or a preferred design.

Canonical pipeline:

`Brief → Extracted Requirements → Confirmed Requirements + Assumptions → Architectural Program → Planning Envelope → Concept Alternatives`

Every derived artifact records its source project version, World Model hash, engine/config version, and deterministic output hash where applicable.

## S2 invariants

1. **No fabricated user requirements.** Extracted requirements are traceable to source text. Missing information stays missing.
2. **No hidden assumptions.** Defaults are explicitly labelled as assumptions and never presented as regulatory facts.
3. **Human confirmation gates commitment.** Extracted requirements remain unconfirmed until accepted or rejected by a user.
4. **Contradictions block downstream generation.** Conflicting hard requirements cannot silently resolve themselves.
5. **Server authority.** The browser may preview edits, but canonical brief, requirements, program, envelope, and alternatives are server-owned.
6. **Determinism.** The same canonical inputs and engine/config versions reproduce the same program/envelope/concept hashes.
7. **Revision binding.** Changing the site or canonical World Model makes dependent S2 artifacts stale rather than silently reusing them.
8. **Evidence before regulation.** Planning values require a source/evidence reference and applicability. Engine defaults are design parameters, not regulations.
9. **Alternatives are not certification.** Concept metrics and constraint checks are preliminary design information, not planning approval or code certification.

## Seven implementation PRs

### PR 60 — S2 roadmap and acceptance contract
- Establish the stage contract, boundaries, artifact lineage, deterministic versioning policy, and explicit non-goals.
- Add a golden S2 benchmark definition and acceptance thresholds.

### PR 61 — Brief Workspace persistence
- Add version-scoped brief read/write API around the existing `BuildingBriefRecord`.
- Canonicalize text, compute SHA-256 content identity, preserve revision history, and expose source metadata.
- Prevent cross-project/version writes and preserve auditability.

### PR 62 — Requirements extraction + confirmation
- Persist deterministic extraction results as `RequirementRecord` rows.
- Preserve source text, extraction method, confidence, provenance, contradiction groups, and status.
- Add accept/reject operations with version binding.
- Rebuild the World Model only from committed requirement state; unconfirmed candidates cannot affect canonical design state.

### PR 63 — Architectural Program
- Introduce a deterministic program contract: space types, quantities, target areas, ranges, public/private/service classification, and adjacency relationships.
- Derive program from confirmed requirements with explicit assumptions for missing architectural detail.
- Validate incomplete inputs and invalid adjacency references.
- Persist the program as a version-scoped artifact with a reproducible hash.

### PR 64 — Deterministic planning envelope
- Convert canonical site geometry plus planning parameters into a buildable polygon using a local metric projection.
- Apply setbacks, coverage, maximum height, FAR/FSI, and maximum GFA constraints when authoritative values are supplied.
- Produce explicit violations/unknowns instead of inventing missing planning rules.
- Persist envelope provenance and input hashes.

### PR 65 — Concept alternatives and explorer contract
- Generate materially different massing strategies from the current canonical World Model, with program/envelope prerequisites.
- Keep the existing deterministic design engine as the execution authority.
- Enforce envelope limits after generation and persist program/envelope provenance on alternatives.
- Expose metrics, assumptions, constraint results, trade-offs, and hashes; never return an opaque AI score.

### PR 66 — S2 backend acceptance contract
- Add deterministic tests for brief → requirements → program → envelope → concept strategy contracts.
- Verify no-fabrication behavior and explicit UNKNOWN planning inputs.
- Document the implemented backend stage boundary.
- The authenticated browser workflow is the remaining S2 surface and should be implemented as the next UI PR set rather than being falsely marked complete here.

## Detailed acceptance criteria

### Brief
- Version-scoped persistence works for create, replace, read, and history.
- Content hash changes iff canonical brief content changes.
- Source metadata is preserved.

### Requirements
- Every extracted requirement has source text and extraction method.
- No extracted value can be marked confirmed without an explicit user operation.
- Contradictory values are surfaced, not averaged or silently selected.
- Benchmark requirements are either extracted or explicitly reported missing.
- No benchmark requirement is fabricated when absent from the brief.

### Program
- Every space has stable identity, type, quantity, area target/range, and provenance.
- Every adjacency references real spaces and has an explicit relationship type.
- Area totals reconcile with target GFA when a target is known; otherwise the gap is an explicit unknown/assumption.

### Envelope
- Geometry is valid and deterministic.
- Setbacks never expand the buildable region.
- Coverage/FAR/height constraints are evaluated from canonical geometry/parameters.
- Missing regulatory inputs remain UNKNOWN.
- Envelope hash changes whenever any canonical input changes.

### Concepts
- Three distinct strategy families exist: balanced, compact, and low-rise.
- Each alternative has geometry, metrics, constraints, assumptions, unknowns, trade-offs, and provenance.
- Selection is a human design-direction decision, never an automatic approval.

## Explicit non-goals for S2

- Universal natural-language command bus (S3).
- Full semantic building editing (S4).
- Production 3D/2D unified editor (S4).
- Construction drawings compiler (S4/S5).
- Full structural, daylight, energy, accessibility, or code certification (S5+).
- IFC/CAD round-trip (S6).
- Collaboration and AI Copilot (S7).

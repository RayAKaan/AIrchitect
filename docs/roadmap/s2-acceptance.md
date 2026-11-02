# S2 Acceptance Contract

S2 provides an authenticated, server-authoritative workflow:

`brief → extracted requirements → confirmed requirements → architectural programme → planning envelope → concept alternatives → evaluation → human selection → design-direction approval`

## Verified implementation contracts

- Brief content is version-scoped, normalized and hashed.
- Requirement candidates retain source text, extraction method and candidate confidence.
- Extracted requirements remain unconfirmed until an explicit user action; contradictions and missing information remain visible.
- Programme spaces have stable IDs, quantities, area targets/ranges, use categories, and explicit adjacency edges.
- Programme allocations reconcile to target GFA; provisional building-use defaults are labelled assumptions.
- Site dimensions and orientation/frontage context are carried forward; missing orientation/frontage remains UNKNOWN.
- Setback geometry is calculated in a local metric projection.
- Footprint coverage and FAR/GFA are separate limits with separate units and checks.
- Unknown or unusable planning-rule values are not silently applied.
- Geometric long-axis orientation is derived from site geometry; solar exposure, prevailing wind and climate remain UNKNOWN without authoritative context.
- Concept generation requires a committed World Model plus current programme and envelope artifacts.
- Concept generation consumes the actual programme and envelope payloads, not only their hashes.
- Candidate evaluation enforces FAR/GFA, footprint coverage, buildable-area and maximum-height limits.
- Alternatives retain programme schedule, adjacency, assumptions, unknowns, engine versions and exact input lineage.
- Stale programme/envelope/World Model combinations are rejected.
- Comparison reports constraint pass/fail/unknown counts and Pareto trade-offs; it does not invent a weighted overall score.
- Selection is a human design-direction decision.
- Separate design-direction approval is restricted to project owners and organization admins, is idempotent and auditable.

## Stage boundary

S2 generates preliminary architectural programmes, planning envelopes and massing alternatives. It does not claim:

- room-level floor-plan geometry or exact placement inside arbitrary irregular site polygons;
- verified solar/daylight, wind or climate simulation where authoritative inputs are absent;
- planning approval, code compliance, engineering sign-off or construction approval;
- construction-ready drawings, full structural/energy/accessibility analysis, IFC round-trip or production collaboration.

The authenticated browser workflow is part of S2. A stage completion claim requires all Phase 2 hardening PRs to be merged and the full CI workflow to pass.

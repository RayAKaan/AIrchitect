# S2 Completion Contract

**Stage:** S2 — Brief → Requirements → Program → Envelope → Concepts
**Status:** Implemented

The S2 browser surface now exposes the complete canonical workflow over the backend contracts implemented in PRs #60–#66:

1. Brief — version-scoped canonical source text and provenance.
2. Requirements — deterministic extraction with explicit human confirmation/rejection.
3. Program — deterministic spaces, area targets/ranges and adjacencies.
4. Envelope — deterministic buildable geometry from explicit planning inputs, with UNKNOWN values preserved.
5. Concepts — deterministic alternatives, comparison, trade-offs and human selection.

## Completion invariants

- Browser state never becomes the source of truth.
- Every stage is tied to the selected project version.
- World Model changes are visible through the canonical refresh boundary.
- Requirement extraction does not confirm requirements.
- Missing planning rules remain UNKNOWN.
- Concept generation is blocked until the canonical version is committed.
- Concept selection requires an explicit human rationale.
- No UI language claims planning approval, code certification, engineering approval or construction readiness.
- S2 entry points have authenticated browser acceptance coverage.

## Remaining scope

S3 begins the universal command/intent and dependency-aware regeneration layer. S2 does not include a universal natural-language command bus, full semantic building editing, production 3D/2D editing, drawing compilation, full engineering analysis, IFC/CAD round-trip, collaboration, or AI Copilot.

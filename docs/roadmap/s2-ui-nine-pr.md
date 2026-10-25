# S2 UI completion — nine-PR implementation plan

S2 backend contracts are implemented through PR #66. The remaining work is the authenticated browser workflow. These nine PRs complete that surface without moving architectural authority into the browser.

## PR 67 — Workflow shell
Establish a dedicated S2 workspace flow inside the existing versioned FoundationWorkspace. Add explicit stage navigation, dependency/status summary, and server-refresh behavior. Keep Site/World Model/Design surfaces intact.

## PR 68 — Brief workspace
Turn the existing brief textarea into a version-aware workspace with source metadata, revision/hash visibility, dirty-state handling, save/analyze actions, loading/error states, and clear human-review language.

## PR 69 — Requirements review
Build a requirements review surface over the existing extraction API. Show source evidence, normalized values, confidence, contradiction state, missing information, and explicit Confirm/Reject actions. Never auto-confirm.

## PR 70 — Program workspace
Add an architectural-program UI that invokes the deterministic program generator and renders spaces, quantities, area targets/ranges, classifications, adjacencies, assumptions, provenance and validation state.

## PR 71 — Envelope workspace
Add planning-envelope inputs and generation UI. Surface authoritative-vs-unknown planning values, setback/coverage/FAR/height controls, geometry/metrics, violations, provenance and deterministic output hash. Never imply unknown rules are approved.

## PR 72 — Concept generation
Connect the UI to the design generation API. Show generation progress/errors and block generation until the canonical version is committed and prerequisites are current.

## PR 73 — Concept explorer
Build A/B/C concept comparison and selection. Show strategy, massing parameters, metrics, constraints, assumptions, unknowns, trade-offs and provenance. Selection is an explicit human design-direction action.

## PR 74 — S2 resilience/accessibility
Harden all S2 surfaces for stale artifacts, retries, empty states, keyboard navigation, ARIA semantics, disabled states, and server/client mismatch. Add focused frontend tests for critical state transitions.

## PR 75 — End-to-end S2 acceptance
Add authenticated browser acceptance for Brief → Requirements → Program → Envelope → Concepts, deterministic backend/browser contract checks, and the final S2 completion document. S2 is complete only when all gates pass.

## Cross-cutting invariants
- Server remains authoritative for canonical state.
- Browser state is presentation/interaction state only.
- No AI-generated or extracted requirement is silently committed.
- Missing regulatory data remains UNKNOWN.
- Stale upstream artifacts block current downstream generation.
- All current results remain tied to project version and World Model hash.
- No S2 UI claims planning approval, code compliance, engineering certification, or construction readiness.

# Phase 25 — Designer-Controlled Semantic Editing & Selective Regeneration

**Status:** Implemented; PR #7 is open and unmerged. CI run [#293](https://github.com/RayAKaan/AIrchitect/actions/runs/38081911968) passed all required jobs on this source tree.  
**Base:** `main` at Phase 24 merge commit `f674bd474f3df58d2087b62b812a8e54cb6333fb`.  
**Phase 24 prerequisite:** PR #6 is merged; CI run #130 passed all jobs.

## Objective

Turn the Phase 24 semantic graph into a controlled editing workspace. Designers must be able to change explicitly editable properties, author and remove architectural components, protect critical elements, understand downstream effects, selectively refresh affected parametric feature intents, and undo/redo changes without mutating committed history or losing provenance.

## Repository-grounded findings

- Phase 24 provides stable semantic IDs, typed properties, semantic relationships, and a deterministic parametric CAD-intent compiler.
- Project versions and World Model revisions are hash-verified; committed and superseded versions are immutable.
- Requirements and assumptions rebuild the canonical World Model. Designer changes therefore need an explicit, persisted override layer that is reapplied after a rebuild rather than an in-memory patch that disappears on the next brief submission.
- CAD jobs and design alternatives bind to the whole World Model hash. The current CAD worker does not expose a verified per-element solid-edit API; Phase 25 must not pretend that refreshing an intent is the same as regenerating a B-rep or STEP/IFC/GLB file.

## Work packages

1. **Validated semantic editing**
   - Define server-owned allowlists, types, units, and bounds for editable Site, Building, Storey, Space, ParkingFacility, Wall, Slab, Roof, Door, and Window properties.
   - Reject unknown fields, invalid/non-finite values, no-op changes, missing elements, stale revisions, and edits to locked elements.
   - Keep canonical Site/Building/Storey entities protected from deletion. Let designers author explicit spaces and architectural components with stable IDs, provenance, and valid relationships.
   - Keep derived values and consistency findings coherent when floor count, floor-to-floor height, or explicit building height changes. Preserve locked storey geometry during upstream changes, distribute remaining GFA only across eligible storeys, and surface irreconcilable floor-area totals.

2. **Version safety and persistence**
   - Permit edits only on DRAFT versions. Use expected revision checks and database row locking for concurrent writers.
   - Append a hash-verified World Model revision for each state mutation and an audit event identifying the actor, operation, target, reason, and resulting hash.
   - Persist designer-authored elements, locks, history, and explicit property overrides in the canonical revision payload.
   - Reapply overrides on subsequent requirement/assumption rebuilds and inherit designer state when creating a new version. An explicit change supplied for a new version supersedes the inherited override for that same parameter.
   - Preserve historical versions; no in-place edits to COMMITTED or SUPERSEDED versions.

3. **Locks and dependency protection**
   - Support explicit lock/unlock with a required reason and audit trail.
   - Reject direct edits/deletes on locked elements.
   - Reject a floor-count reduction that would remove a locked storey.
   - Mark locked elements as protected during selective regeneration and never include them in the regenerated intent set.

4. **Undo, redo, and history**
   - Record edit/create/delete actions with before/after snapshots, actor, reason, timestamp, and impacted downstream groups.
   - Provide undo/redo as new append-only history events; do not erase history.
   - Restore previous override state as well as values, including the distinction between a designer override and a value originally derived from requirements/assumptions.
   - Enforce optimistic revision checks for undo and redo and respect locks.

5. **Selective regeneration and impact**
   - Compute the affected semantic elements and downstream groups from the selected element and relationship graph.
   - Compile only the requested, unlocked elements into deterministic parametric feature intents; return missing inputs and protected element IDs explicitly.
   - Bind each result to the exact World Model hash and reject stale requests.
   - Record regeneration requests in the audit log.
   - State clearly that this operation refreshes feature-intent specifications only; the existing native CAD worker remains responsible for real solids and exchange files.

6. **Designer workspace**
   - Add a usable semantic editor for selecting elements, viewing typed properties, editing values with a reason, creating components, locking/unlocking, deleting authored components, and undoing/redoing.
   - Show element provenance/mapping, recent history, impact preview, protected elements, and selective regeneration results.
   - Disable editing controls for committed/historical versions while retaining read-only inspection and regeneration-intent preview where valid.

7. **Verification**
   - Unit tests: validation bounds, no-op edits, override restoration, undo/redo, lock behavior, locked-storey protection, authored component relationships, typed CAD-intent readiness, and selective target handling.
   - API tests: tenant/version scoping, draft-only writes, expected-revision conflicts, history persistence, lock/unlock, override persistence across brief rebuilds, and regeneration hash binding.
   - Run full repository CI: Ruff/pytest, PostgreSQL migration cycle, frontend lint/tests/build, API/web Docker builds, Compose readiness/smoke, CAD/BIM licence policy, requirements benchmark, and release preflight.
   - Record the exact CI run and unresolved deployment limitations in this plan, completion report, and tracker.

## Definition of Done

- [x] Editable properties have server-owned types, units, and bounds; invalid edits fail without partial mutation.
- [ ] Designer-authored components have stable IDs, typed properties, provenance, and valid semantic relationships.
- [ ] Locks prevent edits/deletes and protect components from selective regeneration.
- [ ] A floor-count edit cannot silently delete a locked storey.
- [ ] Every mutation is revision-checked, audited, and included in a verified World Model hash.
- [ ] Explicit designer overrides survive World Model rebuilds and are correctly superseded by explicit new-version changes.
- [ ] Undo/redo restore values and override semantics, append history, and obey locks.
- [ ] Impact preview identifies affected elements/groups and reports protected elements.
- [ ] Selective intent regeneration is deterministic, only includes eligible requested elements, and rejects stale World Model hashes.
- [ ] The UI is integrated with the canonical version flow and does not allow edits to immutable versions.
- [ ] The full CI suite passed on the implemented source tree (run #293); PR checks must remain green after any commit-history consolidation.

## Explicit boundaries

Phase 25 provides designer-controlled semantic editing and selective parametric feature-intent refresh. It does not claim per-element native B-rep editing, STEP/IFC/GLB export, structural adequacy, regulatory approval, or professional engineering certification. Those outputs require the existing CAD worker, downstream interoperability work, and qualified human review.

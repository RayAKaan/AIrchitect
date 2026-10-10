# Phase 25 Completion Report — Designer-Controlled Editing & Selective Regeneration

**Status:** Implemented; automated acceptance passed on the open Phase 25 pull request.  
**Pull request:** [PR #7 — Phase 25: designer-controlled editing and selective regeneration](https://github.com/RayAKaan/AIrchitect/pull/7) (open; not merged).  
**Branch:** `feat/phase-25-designer-controlled-editing`.  
**Base:** Phase 24 merge commit `f674bd474f3df58d2087b62b812a8e54cb6333fb`.

## Delivered

- Server-owned property allowlists, types, units, plausibility bounds, no-op checks, and optimistic revision checks for semantic edits.
- Designer-authored Space, Wall, Slab, Roof, Door, and Window elements with stable IDs, typed properties, provenance, and validated building/storey/host relationships.
- Explicit wall-host assignment for doors and windows. Openings without a valid host or components without storey placement remain underconstrained rather than being marked CAD-ready.
- Lock/unlock with audit reasons, ancestor-lock propagation, and protection against edits, deletes, undo/redo, or regeneration that bypass locks.
- Floor-count safeguards that prevent removal of locked storeys and prevent orphaning authored components.
- Locked storey values remain protected when upstream GFA or floor-height changes occur. Remaining GFA is distributed across unlocked/unoverridden storeys; incompatible fixed areas surface a review finding.
- Hash-verified World Model revisions, append-only history, actor/reason audit events, undo/redo that restores override provenance, and row-locked version mutations.
- Designer overrides persist across brief/assumption rebuilds and inherit into new versions. Explicit new-version changes supersede the matching inherited override.
- Transitive impact previews distinguish upstream effects from downstream regeneration candidates. Selective regeneration is bound to the exact World Model hash and excludes protected targets.
- Parametric feature intents now include storey placement, per-storey area/elevation/floor-height values, explicit missing inputs, and review warnings for incompatible area targets.
- Responsive Semantic Model editor integrated with the canonical Foundation workspace, including property editing, component authoring, host assignment, lock controls, undo/redo, history, impact preview, and intent refresh.
- Canonical consistency findings are visible in the workspace; immutable versions remain read-only.

## Automated acceptance evidence

**GitHub Actions run [#293](https://github.com/RayAKaan/AIrchitect/actions/runs/38081911968) passed all jobs** on the implemented source tree.

| Gate | Result |
|---|---|
| Backend tests | **427 passed, 40 skipped, 2 warnings** |
| Ruff | Passed |
| PostgreSQL migration cycle | Upgrade/downgrade/upgrade passed |
| Frontend | **17 tests passed**; lint and production build passed |
| API and web Docker images | Both built successfully |
| Docker Compose | Startup/readiness and API smoke checks passed; teardown passed |
| CAD/BIM licence policy | CI policy check passed; 3 copyleft components accounted for |
| Requirements benchmark | **10/10 exact-match cases; precision 1.0000, recall 1.0000, F1 1.0000** |
| Release preflight | Passed |

The requirements benchmark is a ten-case committed fixture corpus. Its score is not a claim of universal natural-language understanding.

## Correctness boundaries and remaining release gates

- Edits are allowed only on DRAFT versions. COMMITTED and SUPERSEDED versions remain immutable.
- Selective regeneration compiles deterministic semantic feature-intent specifications only. It does **not** execute the native CAD worker or claim to produce B-rep solids or STEP/IFC/GLB files.
- Underconstrained geometry and dimensional conflicts are reported for review; the platform does not certify structural adequacy, zoning, fire/life-safety, code compliance, or professional engineering decisions.
- Phase 22 native CAD-host smoke verification and complete redistribution/source-material notices plus qualified legal sign-off remain open release gates. A passing CI licence-policy check is not legal clearance.

## Final verification

PR #7 remains open and unmerged for the repository owner to review. The same source tree has passed the complete required CI suite; after commit-history consolidation, the PR's latest checks must remain green before merge.

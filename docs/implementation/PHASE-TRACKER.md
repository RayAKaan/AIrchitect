# MVP Phase Tracker

| Phase | Name | Status | Exit evidence |
|---:|---|---|---|
| 0 | Repository Audit | Partial | Phase report exists; master audit/traceability now added; SBOM/license gates remain. |
| 1 | Development Foundation | Partial | Compose/runtime scaffolding exists; clean install, lockfiles, migration wiring and container validation remain. |
| 2 | Identity and Project Core | Partial | Auth, org/project APIs and models exist; PostgreSQL integration, tenant-isolation tests, revocation/invites remain. |
| 3 | World Model | Partial | Typed schema and revision routes/models exist; persisted concurrency and downstream artifact binding remain. |
| 4 | Requirements Intelligence | Partial | Deterministic parser and endpoint exist; document extraction and full UI loop remain. |
| 5 | Assumptions and Clarifications | Partial | Assumption lifecycle/API exists; unified revision/stale lifecycle and UI remain. |
| 6 | Decision Runtime | Partial | Provider contract and deterministic fallback exist; durable audit and live provider contract verification remain. |
| 7 | Workflow Runtime | Partial | Persisted DAG/task APIs exist; atomic claims, leases/recovery and handler execution remain. |
| 8 | Geometry Engine | Partial | Deterministic cuboid massing exists; artifact persistence, revision binding and polygon support remain. |
| 9 | 3D Viewer | Partial / Blocked | Interactive viewer shell exists; WebGL confirmation, frontend build and browser QA remain. |
| 10 | Quantities and Cost | Partial | Deterministic sourced-rate estimator exists; persisted geometry-derived quantities and immutable records remain. |
| 11 | Structural Workflow | Partial | Conceptual structural output exists; verified geometry binding and engineering review remain. |
| 12 | Regulatory Engine | Partial | Configurable rule evaluator exists; authoritative ruleset, applicability and persistence remain. |
| 13 | Change Impact | Partial | Dependency impact analysis exists; persistent graph and atomic mutation-driven propagation remain. |
| 14 | Validation and Evidence | Partial | Validation/evidence aggregation exists; immutable persisted cross-domain runs remain. |
| 15 | Review and Deliverables | Partial | Review and PDF/JSON endpoints exist; verified assembled immutable packages remain. |
| 16 | Frontend Integration | Partial / Blocked | React workspace shell exists; dependencies/build and full domain UI journey remain. |
| 17 | Testing and Release | Partial / Blocked | API unit suite and preflight exist; DB/E2E/security/container/deployment gates remain. |
| 18 | CAD/BIM Geometry Pipeline | Delivered (pipeline implementation) | Isolated OCCT/FreeCAD worker, IFC/GLB/STEP export, bounded execution, durable job/artifact persistence, tenant-scoped APIs; remaining cross-domain authority work is tracked in Phase 19. |
| 19 | Geometry Authority & Legacy Path Elimination | In progress (CAD-authority core merged; remaining audit items open) | CAD-only engineering/API/viewer, explicit geometry source, downstream dependency/staleness handling; remaining legacy-path retirement and production toolchain verification tracked in the Phase 19 audit. |
| 20 | End-to-End MVP Integration | Delivered (PR #2; CI run #71 passed) | Feasibility workflow generates/reuses current hash-bound CAD and GLB before engineering, assembles evidence, requires human review, refreshes frontend caches, and has end-to-end API coverage. Native production CAD toolchain remains deployment-specific. |
| 21 | Production Hardening & MVP Release | Delivered (PR #3; CI run #94 passed) | Production configuration guardrails, request correlation/security headers, configurable Compose, database-aware readiness, and API/web/Docker/Compose/release-preflight CI. Native CAD deployment and legal release clearance remain separate gates. |
| 22 | CAD Foundation, Licensing & Runtime Reliability | Implementation merged; operational gates open | PR #4 merged; CI run #100 passed. Manifest-backed licence policy, dependency metadata checks, native CAD smoke command, and release-preflight wiring are merged. Native-host smoke evidence, complete redistribution notices/source materials, and qualified counsel sign-off remain open. |
| 23 | Requirements Accuracy, Constraint Validation & Benchmarks | In progress | Context-aware extraction, exact-value versus inequality handling, persisted validation evidence, cross-field checks, benchmark fixtures with precision/recall/F1 gates, and UI review warnings. CI gates remain. |

## Rules
- A phase is complete only with implementation evidence, tests, limitations, and Definition of Done confirmation.
- Never count scaffolding, placeholders, simulated progress, or unverified external data as completion.
- Keep this tracker updated as work progresses.

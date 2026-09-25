# Phase 0 — Repository Audit & Open-Source Discovery

**Product:** Standalone building feasibility platform under Nazmak  
**Blueprint:** Master Technical Specification v1.0  
**Phase status:** PARTIALLY COMPLETE — greenfield baseline established; dependency/license verification and environment validation remain gates.

## 1. Audit Scope and Findings

### Workspace baseline
- No pre-existing application repository, source files, tests, package manifests, or project-specific documentation were present in the supplied sandbox workspace at audit time.
- No existing implementation was modified or overwritten.
- A new greenfield workspace is being established at `nazmak-building-platform/`.
- No claim is made that a remote GitHub repository was audited. A repository URL or mounted source is required to audit an existing codebase.

### Initial architecture decision
Use a modular monolith with FastAPI and a React/Vite TypeScript frontend, PostgreSQL/PostGIS for canonical state and supported spatial operations, local S3-compatible/object-storage abstraction, deterministic domain engines, and isolated worker execution. Keep provider-specific AI integration behind an internal Decision Runtime. Preserve the option to adopt Temporal after a Phase 1 spike; do not make the application domain depend on Temporal APIs.

## 2. Open-Source Reuse Candidates

These are candidates, not blanket approvals. Before pinning dependencies, verify the exact repository, release/tag, LICENSE file, transitive dependency licenses, security posture, and compatibility. Preserve upstream notices and generate an SBOM/license report in CI.

| Component | Candidate | Intended use | License posture / decision |
|---|---|---|---|
| React Three Fiber | `pmndrs/react-three-fiber` | React renderer for Three.js | Commonly MIT; verify exact pinned release and dependencies before adoption. |
| Three.js | `mrdoob/three.js` | Browser 3D rendering | MIT; verify release and notices. |
| Temporal Python SDK | `temporalio/sdk-python` | Durable workflow orchestration candidate | MIT; evaluate with Temporal server/runtime operational requirements. |
| FastAPI | `fastapi/fastapi` | HTTP API framework | MIT; adopt. |
| Pydantic | `pydantic/pydantic` | Typed contracts and validation | MIT; adopt. |
| SQLAlchemy | `sqlalchemy/sqlalchemy` | Persistence/ORM | MIT; adopt. |
| Alembic | `sqlalchemy/alembic` | Database migrations | MIT; adopt. |
| TanStack Query | `TanStack/query` | Frontend server-state synchronization | MIT; adopt. |
| React Router | `remix-run/react-router` | Frontend routing | MIT; adopt. |
| Zod | `colinhacks/zod` | Frontend schema validation | MIT; adopt. |
| Vitest | `vitest-dev/vitest` | Frontend unit tests | MIT; adopt. |
| Playwright | `microsoft/playwright` | Browser E2E tests | Apache-2.0; adopt after browser/runtime review. |
| OpenTelemetry Python | `open-telemetry/opentelemetry-python` | Tracing/metrics | Apache-2.0; adopt incrementally. |
| GeoLens | `geolens-io/geolens` | Reference only for FastAPI/PostGIS/geospatial patterns | Apache-2.0 reported upstream; not adopting wholesale due to product mismatch and its own architectural choices. |

### Explicit exclusions / caution
- Do not pull in a full BIM/CAD kernel merely for MVP massing.
- IfcOpenShell is LGPL-3.0-or-later per the blueprint and is excluded absent legal approval.
- OpenSees requires legal and technical review before commercial use.
- Do not import datasets, models, sample assets, or binaries without separately checking their licenses and attribution terms.
- The license of a repository does not automatically cover all bundled assets or dependencies.

## 3. Preliminary Reuse Strategy

Reuse commodity frameworks and infrastructure libraries. Build purpose-specific capabilities in-house:
- Canonical Building World Model and version semantics
- Requirements/assumptions lifecycle
- Deterministic parameter-driven massing generator and geometry contracts
- Quantity and cost calculation rules with explicit data provenance
- Regulatory rule schema/evaluator (configured rules only)
- Artifact dependency graph, stale propagation, and rerun planning
- Evidence, validation, review, and issuance lifecycle
- Feasibility-package assembly

## 4. Phase 0 Decisions / Open Questions

| ID | Decision or question | Initial disposition |
|---|---|---|
| D-001 | Existing repository to preserve? | No repository was present in the supplied workspace. Greenfield path selected unless user supplies one. |
| D-002 | Workflow runtime | Keep behind an internal interface; run a Temporal feasibility spike in Phase 1 before final selection. |
| D-003 | Local object storage | Use an adapter with filesystem development implementation first; S3-compatible implementation later. |
| D-004 | AI provider | Deterministic mode is the baseline; Jev/LLM integration is optional and adapter-isolated. |
| D-005 | Saudi rates/rules | No fabricated defaults. Seed only clearly labeled illustrative values or unknown rules until sourced/configured. |
| D-006 | Product name | Undecided; use neutral platform naming in code and UI. |

## 5. Phase 0 Exit Gates

- [x] Supplied workspace inspected; no existing project files found.
- [x] Greenfield decision recorded without claiming remote-repository audit.
- [x] Initial stack and modular-monolith direction recorded.
- [x] Reuse candidates identified with license caveats.
- [ ] Exact dependency versions and transitive licenses verified against selected releases.
- [ ] Dependency/SBOM automation configured.
- [ ] Phase 1 environment and workflow-runtime spike completed.

## 6. Required User Input (only if applicable)

If there is an existing GitHub repository that should be preserved, provide its URL or attach/mount it. Otherwise implementation proceeds in the new greenfield workspace.

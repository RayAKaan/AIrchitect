# Phase 22 — CAD Foundation, Licensing & Runtime Reliability

**Status:** In progress. This phase is not complete until native CAD smoke evidence and release obligations are closed.
**Baseline:** Phase 21 is merged to `main`; CI run #94 passed. Phase 18 provides the isolated CAD/BIM worker, and Phase 19–20 enforce CAD authority through the feasibility workflow.

## Objective

Establish a reproducible and auditable CAD execution foundation for later semantic geometry and editing work. Keep the API/worker isolation boundary, use real CAD output as the geometry authority, and make dependency/licensing drift visible before it reaches a release.

## Repository-grounded audit

The repository already contains:

- `apps/api/app/domains/cad/{capability,config,runner,orchestrator,persistence,storage}.py` for capability discovery, worker configuration, bounded execution, orchestration, and artifact persistence.
- `apps/api/app/cad_worker/` for isolated worker execution and FreeCAD/OCCT/IFC/GLB/STEP handling.
- `apps/api/app/domains/cad/toolchain_manifest.json` and `tools/cad/generate_toolchain_manifest.py` for recorded versions and licence metadata.
- `apps/api/tests/test_phase18_runner.py`, `test_phase18_worker_protocol.py`, `test_phase18_worker_live.py`, `test_phase18_isolation.py`, and related tests for subprocess containment and real-toolchain checks.
- `docs/legal/PHASE-18-OPEN-SOURCE-LICENSE-AUDIT.md`, which identifies missing redistributable licence materials, incomplete transitive metadata, and required counsel sign-off.

The main gaps addressed by this PR are that CI did not enforce the committed copyleft inventory, the manifest generator emitted a null licence for IfcOpenShell despite having a licence classifier, and there was no single portable command for operators to run a real geometry smoke test against their configured native toolchain.

## Work packages

### 22.1 — CAD execution audit
- Preserve the single bounded subprocess runner and separate worker virtual environment.
- Keep missing kernels, timeouts, malformed artifacts, and invalid solids as explicit failures.
- Use the existing runner/protocol regression suite; do not replace the real worker with a mock in the operator smoke test.

### 22.2 — Dependency and licence policy
- Normalize the manifest's copyleft entries using effective licence metadata.
- Maintain a reviewed allowlist of exact component/version/licence triples.
- Fail CI for unreviewed copyleft components, unexpected licence markers, missing required core components, or completely untraceable licence metadata.
- Warn on incomplete normalized identifiers when a licence file is recorded; strict release mode blocks on warnings.
- Keep legal clearance separate from CI approval.

### 22.3 — Reproducible native CAD smoke command
- Probe the actual configured worker capabilities.
- Build a known 10 × 8 × 3.5 m prism through the real CAD runner.
- Verify a valid, closed solid, one solid topology, analytical volume (280 m³), surface area (286 m²), bounding dimensions, and non-empty STEP/GLB artifacts.
- Validate IFC when IfcOpenShell is available, or require it with an explicit command-line flag.
- Provide a strict flag for deployments that require FreeCAD as well as OCCT.

### 22.4 — CI and release-preflight wiring
- Run the static licence policy gate in GitHub Actions.
- Test the policy checker with the committed inventory and deliberately unreviewed licence fixtures.
- Make release preflight require the Phase 22 plan/report, policy, notices, checker, and native smoke command.

### 22.5 — Native host and legal release closure
- Run the smoke command on the actual supported deployment host; record OS, Python, OCCT/FreeCAD/IfcOpenShell versions, measurements, and artifact hashes.
- Add complete required licence texts/source pointers to the redistributable bundle and review the complete FreeCAD archive inventory.
- Obtain qualified legal counsel's written countersignature before commercial redistribution.

## Acceptance criteria

- [x] The CAD/BIM copyleft inventory is checked by CI against exact reviewed package/version/licence entries.
- [x] The manifest generator uses effective licence metadata instead of emitting a null copyleft licence.
- [x] CI tests detect an unreviewed copyleft addition and untraceable licence metadata.
- [x] A real native-toolchain smoke command exists and validates geometry against closed-form expectations.
- [x] Release preflight requires Phase 22 evidence and licence policy artifacts.
- [ ] The smoke command passes on the actual supported native CAD deployment host; CI's fake-worker tests are not a substitute.
- [ ] Complete licence texts and any required source offer/pointers are included in the redistributable toolchain bundle.
- [ ] Qualified counsel signs off on the actual distribution and process-isolation model.

## Verification boundaries

The ordinary GitHub-hosted Linux CI runner does not provision the pinned Windows FreeCAD archive or the isolated CAD worker virtual environment. This PR can verify the policy gate, Python tests, API/frontend/container workflows, and that the native smoke command is syntactically/import correct; it cannot truthfully claim that native CAD execution passed on the production host. The smoke command is intended to produce that missing evidence.

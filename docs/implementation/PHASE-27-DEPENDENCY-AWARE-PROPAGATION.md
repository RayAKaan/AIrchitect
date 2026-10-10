# Phase 27 — Dependency-Aware Feasibility & Change Propagation

**Status:** Implementation in progress on `feat/phase-27-dependency-aware-propagation`.
**Base:** `main` after Phase 26 merge.

## Objective

Make the persisted artifact dependency graph authoritative for change-impact analysis and stale-state propagation. Any source mutation that changes the canonical World Model hash must invalidate artifacts derived from the prior hash, and explicit artifact changes must invalidate their transitive dependants atomically.

## Repository-grounded baseline

- `ArtifactVersion` and `ArtifactDependency` already persist artifact identities and dependency edges.
- The feasibility pipeline writes dependency edges, but the legacy change-impact analyzer accepts a client-supplied graph and does not persist its result.
- The existing persisted impact endpoint compares World Model fields and reports existing statuses; it does not calculate dependency paths from persisted edges.
- CAD export manifests compare the current World Model hash with the source hash, but a shared, mutation-driven propagation path is needed across domain artifacts.

## Work packages

1. **Persisted graph authority:** Read only artifact nodes and dependency edges scoped to the authorized project version. Never traverse a cross-project/version edge.
2. **Deterministic impact analysis:** Calculate shortest transitive dependency paths with stable ordering, multiple roots, and cycle protection. Preserve unrelated artifacts.
3. **Atomic stale propagation:** Mark affected ArtifactVersion rows and their domain projections stale in the same database transaction; record an audit event with source hash, changed roots, paths, and resulting statuses.
4. **World Model integration:** When a new World Model revision changes the canonical hash, automatically stale artifacts bound to the superseded revision and their dependants. Mark old successful/in-flight CAD runs stale; do not invalidate artifacts when the canonical hash is unchanged.
5. **Authenticated APIs:** Expose the persisted graph and a guarded propagation endpoint that requires the caller's expected current World Model hash, checks project/version membership, and rejects IDs outside the scoped graph.
6. **Regression evidence:** Cover graph traversal, deterministic paths, cycles, cross-scope edges, optimistic hash conflicts, stale propagation, and domain-status synchronization. Update the release preflight and phase tracker.

## Acceptance criteria

- [ ] Graph analysis uses persisted edges, not client-supplied dependency topology.
- [ ] Cross-tenant and cross-version dependencies are never traversed.
- [ ] A stale expected World Model hash returns a conflict instead of mutating state.
- [ ] A World Model hash change automatically invalidates prior derived artifacts and successful/in-flight CAD runs.
- [ ] Downstream artifact and domain statuses change in one transaction; artifact payloads and hashes remain immutable.
- [ ] Audit metadata preserves changed roots, source hash, dependency paths, and stale IDs.
- [ ] No recomputation is claimed or automatically scheduled; stale work remains explicit until a separate workflow executes it.
- [ ] Backend tests/lint, migration cycle, frontend tests/lint/build, Docker/Compose smoke, CAD/BIM licence policy, requirements benchmark, and release preflight pass.

## Safety boundaries

- Stale propagation is not recomputation; the API explicitly reports that recomputation has not been scheduled.
- Existing artifact payloads and hashes are not rewritten.
- A current hash binding is not proof of architectural, structural, regulatory, or constructability correctness.
- CAD native-host validation and legal redistribution/source-material clearance remain Phase 22 release gates.

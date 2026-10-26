# S4 — Production Artifact Runtime: Next 10 PRs

**Base:** `main` at `ab04c35aae6a03cde20119bc8b3981f39adad75c`

S4 turns the existing deterministic artifact/dependency/regeneration foundation into a production-grade artifact runtime while preserving the repository's canonical-state and fail-closed rules. Every PR is independently mergeable and must reuse existing dependency, provenance, command, workflow, and regeneration infrastructure rather than introducing parallel state machines.

## PR 137 — Workflow task runtime contract
- Define explicit task lifecycle states and legal transitions for persisted `WorkflowTaskRecord`.
- Add a transactional claim/lease repository with deterministic ordering and PostgreSQL `SKIP LOCKED` support.
- Add heartbeat and lease-recovery semantics.
- Add focused SQLite and PostgreSQL integration coverage.

## PR 138 — Durable workflow worker
- Add a single-iteration workflow worker around the task repository.
- Separate claim, execution, and completion transactions.
- Persist structured failure classification and retry/backoff metadata.
- Guarantee failed task execution cannot publish partial artifact state.

## PR 139 — Pipeline stage handlers
- Extract deterministic feasibility stages from the monolithic lifecycle runner into explicit handlers.
- Give each stage immutable input/output contracts and canonical input hashes.
- Preserve existing stage order and outputs.
- Add idempotent stage replay tests.

## PR 140 — Artifact dependency rebinding
- Make successful regeneration create a new `ArtifactVersion` rather than mutating historical identity in place.
- Atomically rebind dependency edges to the new version.
- Retain superseded versions for audit/history.
- Reject cross-project/version dependency rebinding.

## PR 141 — Multi-artifact regeneration handlers
- Register deterministic handlers for planning envelope, geometry, quantities, cost, structural concept, regulatory evaluation, and validation artifacts where authoritative deterministic engines already exist.
- Unsupported or evidence-dependent artifact types fail closed.
- Each handler verifies source revision identity and output hash.

## PR 142 — End-to-end artifact runtime acceptance
- Add a complete command → invalidation → queue → worker → regeneration → dependency-rebind acceptance path.
- Cover repeated execution, concurrent claims, stale source revisions, retry, and lease recovery.
- Assert no partial publication after handler failure.

## PR 143 — Artifact lineage/provenance hardening
- Normalize provenance fields across generated artifacts.
- Persist source revision, dependency hashes, engine/config versions, generation job, and timestamps deterministically.
- Add provenance integrity validation and tamper/mismatch tests.

## PR 144 — Release/readiness gate
- Add a server-authoritative artifact readiness evaluator.
- Block release when required artifacts are stale, failed, unknown, missing provenance, or blocked by human review/evidence requirements.
- Expose machine-readable reasons and dependency paths.

## PR 145 — Operational observability
- Add structured workflow/regeneration metrics and health summaries without making observability state authoritative.
- Expose queue depth, running leases, retry counts, terminal failures, and oldest queued age.
- Keep tenant/project authorization boundaries intact.

## PR 146 — Production runtime integration and documentation
- Wire the worker/runtime boundaries into application startup/worker entry points without implicit schema creation.
- Add production deployment configuration and operational runbook.
- Add final end-to-end regression suite and update architecture/roadmap truth.

## Non-negotiable invariants

- Canonical World Model/revisions remain authoritative.
- AI cannot directly mutate canonical state.
- Derived artifacts remain versioned and auditable.
- Stale artifacts cannot be treated as current.
- Every regenerated artifact is bound to an immutable source revision/hash.
- Historical artifact versions remain queryable.
- Unsupported or insufficiently evidenced operations fail closed.
- PostgreSQL is the deployed authority; SQLite is test/local convenience only.
- No PR is merged on the basis of assumed CI: GitHub Actions must report passing required jobs for the PR head before merge. If Actions do not report a run, the result is explicitly recorded as unverified rather than called passing.

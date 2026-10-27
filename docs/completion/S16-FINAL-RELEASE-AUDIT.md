# S16 Final Release Audit

**Status:** complete on `main` when this audit is merged and CI is green.

## Product boundary

S16 closes the planned product-unification boundary: architect-facing workflow, canonical state, persistence/history, deterministic validation and impact, CAD/BIM and engineering projections, regulatory evidence/verification, and release acceptance are presented as one product workflow rather than disconnected subsystems.

## S16 slices

- **S16.1 — Copilot loop:** proposal → command compilation → deterministic plan → impact → approval token → existing human-approved commit path.
- **S16.2 — Unified workspace:** architect-facing workflow map around the canonical workspace.
- **S16.3 — Synchronization:** typed project-scoped browser event contract for persisted 3D selection synchronization.
- **S16.4 — Version history:** immutable version/revision history and semantic comparison surface.
- **S16.5 — Acceptance:** Playwright scenario covering account/project creation, workspace stages, history, brief persistence and canonical commit.
- **S16.6 — Hardening:** bounded retry policy, explicit stale-revision recovery semantics, and bounded PostgreSQL connection pools.
- **S16.7 — Release gate:** deterministic repository gate plus production-readiness evidence.

## Production safeguards

- Canonical state remains server-authoritative.
- AI proposals cannot directly mutate canonical state.
- Human approval remains required before Copilot commit.
- Stale revisions are conflicts, not blindly retried mutations.
- Production configuration rejects weak authentication/database credentials and legacy geometry execution.
- CI covers API, web, Docker, browser acceptance and release preflight.
- CAD/BIM/regulatory professional claims remain explicitly bounded by the existing evidence and human-review contracts.

## Final acceptance command

```text
python scripts/s16_release_gate.py
python scripts/release_preflight.py
```

The release gate is a repository-integrity gate; successful execution does not itself constitute structural, regulatory, legal or construction certification.

# Integration Defects & Risks — Baseline

| ID | Severity | Finding | Current action / next step |
|---|---|---|---|
| INT-001 | High | Tracker top-level phase statuses conflict with later phase reports and implemented code. | Treat this audit/matrix as the baseline; normalize tracker to partial/unverified states. |
| INT-002 | High | Frontend package uses `latest` dependency declarations and has no lockfile. | Pin compatible versions and produce lockfile after registry access is available. |
| INT-003 | High | Frontend install timed out; no build/lint/test evidence. | Retry in a network-enabled environment or use available cache; keep blocked until success. |
| INT-004 | High | Production DB migration execution is not verified; local `create_all` bootstrap exists. | Add migration baseline and PostgreSQL integration gate. |
| INT-005 | High | Domain artifacts are not yet unified into a persisted dependency graph. | Build artifact/revision registry and mutation-driven stale propagation. |
| INT-006 | High | Workflow runtime lacks verified atomic worker claim/lease/recovery semantics. | Implement PostgreSQL-safe claim and lease expiry with integration tests. |
| INT-007 | Medium | API lifecycle used deprecated `on_event` hooks. | Fixed in this pass using lifespan; API suite passes. |
| INT-008 | Medium | Weak default auth secret could be used outside local mode. | Added startup validation for non-local environments; add dedicated config tests. |
| INT-009 | Medium | Session dependency recreated sessionmaker each request. | Fixed to reuse engine-bound session factory. |
| INT-010 | Medium | SQLAlchemy JSON declarations used dynamic imports. | Fixed with direct JSON import. |

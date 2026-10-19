# Backend test-integrity policy

S0.2 makes skipped tests an explicit engineering concern rather than an invisible CI condition.

## Required checks

The backend CI performs three separate checks:

1. `python scripts/audit_test_skips.py --strict` scans test source for statically declared pytest/unittest skips and requires every discovered skip to have a recognized category.
2. `pytest -q -m postgres -rs` runs the PostgreSQL/PostGIS integration gate against the real CI database.
3. `pytest -q -m 'not postgres' -rs` runs the application suite against SQLite without hiding PostgreSQL-only tests in a skip summary.

The `-rs` flag remains intentional: runtime skips that cannot be detected statically must still be visible in the GitHub Actions log.

## Classification

Every legitimate skipped test belongs to exactly one category:

| Category | Meaning | Required action |
| --- | --- | --- |
| `POSTGRES_REQUIRED` | Requires PostgreSQL/PostGIS semantics or concurrency behavior unavailable in SQLite | Move into the PostgreSQL integration lane; do not leave permanently skipped if CI can run it |
| `NATIVE_CAD_REQUIRED` | Requires FreeCAD, OCCT/OCP, IfcOpenShell, or another native CAD/BIM runtime | Keep as an explicit native-toolchain gate and document the required environment |
| `BROKEN` | Test is expected to exercise supported behavior but currently fails because the test or implementation is broken | Repair it; do not use a skip as a workaround |
| `OBSOLETE` | Behavior is intentionally superseded or removed | Delete the test when the replacement coverage exists |
| `ENVIRONMENTAL` | Behavior depends on a genuinely unavailable OS/runtime/environment capability | Document the environment and provide CI coverage where practical |
| `INTENTIONAL` | Deliberately excluded from ordinary execution for a documented product/release reason | Keep the scope narrow and document why |

`UNCLASSIFIED` is a CI failure. A new skip must never be introduced merely to make a failing suite green.

## Native CAD boundary

The API test suite uses a fake worker for deterministic API orchestration coverage. That does **not** certify the native CAD/BIM stack. Native CAD validation remains a separate release/manual gate until a supported native runtime is available in CI.

## PostgreSQL boundary

The repository previously provisioned PostGIS in CI but executed the main application suite against SQLite. S0.2 adds an explicit PostgreSQL/PostGIS integration lane so migration and deployed-dialect assumptions are exercised against the intended database engine.

The integration gate intentionally starts small: database identity, PostGIS availability, Alembic state, and canonical schema presence. Domain-specific PostgreSQL tests should be moved into this lane as they are identified during the skip audit.

## Audit ownership

The source audit is generated from the repository at test time; this document defines the policy and categories rather than maintaining a manually copied list that can drift from the code. CI logs are the authoritative runtime record for the current skip count and reasons.

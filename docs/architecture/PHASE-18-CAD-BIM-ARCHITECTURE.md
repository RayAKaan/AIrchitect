# Phase 18 — CAD/BIM Architecture

Status: in progress (S1–S9 delivered, S10–S14 open). Last updated 2026-09-27.

## Why this phase exists

AIrchitect's design engine generates geometry as a lightweight intermediate
representation and the viewer draws that representation directly in the browser.
That works for massing studies, but it is not a building. There is no solid model,
no BIM model, no exchange format another tool can open, and no way to measure the
result the way a quantity surveyor or a structural engineer would.

Phases 8–13 of the roadmap each assume a real geometry artifact exists and is
referenced rather than recomputed:

| Phase | Assumption that needs a real geometry artifact |
| --- | --- |
| 8 — Geometry Engine | a solid model, not a bounding-box sketch |
| 9 — 3D Viewer | a mesh the viewer loads instead of fabricating |
| 10 — Quantities | volumes and areas derived from solids |
| 11 — Structural | load paths derived from a real massing |
| 12 — Regulatory | setbacks and envelope checks against real geometry |
| 13 — Change Impact | staleness propagated from a durable artifact |
| 16 — Frontend | provenance and status shown from persisted state |

Phase 18 supplies that artifact. It is a separate phase rather than an extension of
Phase 8 because the constraint that shapes it is not algorithmic: it is legal and
architectural. Getting real CAD kernels into the API process would pull LGPL
components into the application image, so the geometry must run somewhere else
entirely.

## The isolation boundary

The API process contains no CAD or BIM library. `OCP`, `ifcopenshell`, `FreeCAD`,
and `Part` are never imported by application code; `tests/test_phase18_isolation.py`
asserts that importing the API cannot pull one in.

```
   API process                     isolated worker process
   ────────────                    ──────────────────────
   CadJobRequest                   reads request as a plain dict
        │                                  │
        │  runner.py                      │  app.cad_worker.main
        │  - resolves worker venv         │  - validates elements
        │  - scratch dir per job          │  - builds solids (OCCT or FreeCAD)
        │  - subprocess, no shell         │  - tessellates, exports
        │  - time/size limits             │  IFC / GLB / STEP / BREP
        │  - verifies artifacts           │
        ▼                                  ▼
   CadJobResult  ◀── JSON on disk, base64 artifacts ──┘
        │
        │  storage.py  content-addressed, atomic, outside PostgreSQL
        │  persistence.py  CadJobRun + CadArtifact + geometry + validation
        ▼
   PostgreSQL (metadata)   +   artifact root (bytes)
```

Two design consequences are worth stating explicitly.

**The worker does not import the API's protocol module.** It reads a plain `dict`.
That keeps the worker's virtualenv free of pydantic and makes the process
boundary real, but it means nothing forces the two sides to agree. So
`tests/test_phase18_worker_protocol.py` derives the worker's read-set and
content-type table from its source with an AST walk and compares them against the
API's. The first gap it caught was real: `freecad_timeout_seconds` was configured,
validated, and then never transmitted, so the worker's FreeCAD timeout was
permanently 180 seconds.

**A second content-type table existed and disagreed with the worker.** The worker
computes the type of the file it actually produced. An API-side guess was wrong
about FreeCAD documents (`application/vnd.freecad`, not `application/x-freecad`) and
BREP. The API no longer derives content types at all; it stores what the worker
reported and the parity test keeps the two in agreement.

## Persistence

S9 added `cad_job_runs` and `cad_artifacts`.

A `cad_job_runs` row exists for **every** invocation, including rejections,
timeouts, and crashes. A geometry pipeline that cannot explain why a model it did
not produce was rejected cannot be debugged, so the run is recorded with its typed
error code even when nothing was produced.

`cad_artifacts` holds one row per binary: kind, filename, content type, byte size,
SHA-256, and a `storage_key`. The bytes are never in PostgreSQL. They live in the
artifact root under a content-addressed layout:

```
<artifact_root>/cad/<organization>/<hh>/<sha256><extension>
```

Content addressing is not a micro-optimisation. The same geometry is regenerated on
every run, so it deduplicates; and because the file name *is* the hash, a later run
cannot silently change what an earlier database row points at. The organisation
segment keeps tenants physically separated as well as logically, and the two-hex
shard keeps directory sizes bounded.

Writes go to a temporary file in the destination directory and are then renamed into
place, so a reader can never observe a half-written GLB from a crashed run. Reads
verify the content against the name and raise rather than return a wrong answer.

### Binding geometry to the world model

Every artifact carries the `WorldModelRevision` it was computed from, plus that
revision's `model_hash`. The design engine already invalidates alternatives whose
input hash no longer matches; CAD geometry joins the same cascade.

The binding is **re-checked at write time**. A worker run takes real time and the
world model can gain a revision while it is in flight. `record_cad_success`
re-resolves the current revision before committing and, if it has moved, records the
geometry and validation as `STALE` with `world_model_is_current: false` and writes a
`CAD_GEOMETRY_INVALIDATED` audit event. Recording such a result as current would be
a lie that no later reader could detect.

### Identity and reuse

`geometry_artifacts` and `validation_runs` are unique on their content hash within a
project version. The CAD geometry hash is derived from the *measurements*, not the
export bytes, so a re-run that produces the same solids with different tessellation
is correctly recognised as the same geometry and points at the existing row instead
of violating the constraint. The run is still recorded, so the provenance chain
stays intact.

Request hashing deliberately excludes fields that describe the attempt rather than
the geometry — `output_dir`, `sandbox_root`, `freecad_timeout_seconds`, `job_id` —
so the same geometry requested twice with different timeouts hashes identically. Mesh
deflection is *not* excluded, because it changes the GLB.

### Toolchain provenance

Each run stores the toolchain twice over: scalar columns for what is worth querying
(OCCT, IfcOpenShell, and FreeCAD versions) and a `capabilities_json` document holding
everything the worker reported, including the interpreter build and the toolchain
digest. The provider block the worker returns for a result is preferred over a
capability probe, because it is a fact about that run rather than a measurement
taken earlier. A failed run has only the probe, since it never reported a provider.

## Security properties

- The worker runs as a subprocess with no shell, on a job-specific scratch directory
  that is removed in a `finally` block.
- `output_dir` must resolve inside the scratch root. Equality is allowed; traversal
  and prefix-sibling escapes are rejected. Comparison is case-insensitive because
  the root may be on NTFS.
- Artifact extensions come from a fixed kind→extension map, not from the request.
- Request and response payloads are size-limited, and every returned artifact is
  re-verified for size and hash before it is stored.
- `storage_key` resolution refuses absolute paths, backslashes, and `..`, and
  confirms containment against the root. A corrupted row cannot become a read
  outside the artifact root.
- POSIX resource limits are applied to the worker; a per-process memory cap is not
  available on Windows and is currently deferred to the container boundary.
- The licence boundary is enforced by construction rather than by convention — see
  `docs/legal/PHASE-18-OPEN-SOURCE-LICENSE-AUDIT.md`.

## What is verified, and what is not

Verified in CI:

- the isolation boundary (importing the API cannot load a CAD library);
- the runner against a real subprocess, including a real OCCT and FreeCAD run;
- storage properties including traversal refusal, atomic-write cleanup on failure,
  deduplication, and content verification on read;
- persistence against a real database, including failure recording, revision
  binding, staleness on a mid-run revision change, and reuse of identical geometry;
- migration/model parity. The test suite builds its schema from the models, so a
  column added to a model and forgotten in a migration would pass every test and
  then fail on first deploy; the parity test runs the whole Alembic chain against
  SQLite and compares tables, columns, and types.

Not verified, and why:

- **PostgreSQL.** The suite uses SQLite, and no PostgreSQL instance is available in
  this environment. Tenant-scoped query behaviour under real row-level constraints
  is unverified.
- **Docker.** The daemon is unavailable, so the container boundary, the worker's
  resource limits in practice, and the CI container job are unverified.
- **`ifcopenshell.geom` on Python 3.14.4** hangs during iterator construction. IFC
  generation and GLB export are unaffected because they do not use that path, but
  ifcopenshell-based geometry traversal is not usable at this interpreter version.

## Remaining work

- **S10** — API endpoints and orchestration: submit a job, poll it, download an
  artifact with a tenant-scoped, non-disclosing 404 when it is absent.
- **S11** — quantities derived from the persisted solids.
- **S12** — structural and regulatory consumers bound to the geometry artifact.
- **S13** — frontend integration: the viewer loads the persisted GLB instead of
  fabricating geometry, and shows provenance and staleness from persisted state.
- **S14** — container and CI wiring, parity gates against the legacy engine, and
  reconciliation before the scratch-geometry path is removed.

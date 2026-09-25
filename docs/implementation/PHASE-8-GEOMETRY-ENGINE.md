# Phase 8 — Geometry Engine (partial)

## Implemented
- Pydantic-validated geometry request with source revision and bounded massing alternatives.
- Deterministic rectangular/cuboid massing generator, sorted by option ID.
- Derived footprint area, gross floor area, volume, and height in metres.
- SHA-256 hash over canonical mesh vertices/faces; deterministic artifact identifiers.
- Basic positive-dimension/closed-cuboid validation flags.
- Authenticated, organization-membership-protected `POST /api/v1/geometry/generate` endpoint.
- Explicit caveats that setbacks are inputs, not code interpretations, and no compliance/engineering approval is implied.

## Verification
- API test suite: **27 passed**.
- Four existing FastAPI `on_event` deprecation warnings remain.

## Limitations / open gates
- Conceptual rectangular footprints only; no arbitrary site polygon, orientation, boundary clipping, holes, or true site setbacks.
- No floor-by-floor geometry, openings, cores, parking, terrain, or BIM/GLB export.
- Artifacts are returned synchronously and are not persisted or registered as workflow outputs.
- Source revision is caller-supplied; endpoint does not yet verify it against the project's current World Model revision.
- Mesh validation is intentionally minimal; no independent manifold/solid validation library is used.
- No regulatory, structural, fire/life-safety, or engineering evaluation.
- PostgreSQL-backed endpoint/tenant-isolation integration tests not run.

## Status
Partial. This is a deterministic MVP geometry slice, not a production building geometry engine. Phase 9 (3D Viewer) should consume the artifact contract only after persistence/revision binding is addressed or explicitly handled as a later integration gate.

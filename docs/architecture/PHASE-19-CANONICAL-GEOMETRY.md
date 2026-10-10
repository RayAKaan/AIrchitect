# Phase 19 — Canonical Geometry Contract

## Purpose

The persisted CAD boundary representation (B-rep) and the measurements derived from its validated solids are the only authoritative geometry for engineering calculations. The legacy `GeometryIR` is not a substitute for a CAD solid and must never be used to populate quantities, structural/regulatory assessments, validation, or user-facing 3D geometry.

## Canonical artifact identity

A geometry artifact is identified by:
- organization, project, and immutable project-version IDs;
- the bound World Model revision and its hash;
- the design-alternative ID and design hash;
- explicit source: `CAD_BREP` or `LEGACY_IR`;
- CAD job/run ID and validated toolchain provenance for CAD artifacts;
- artifact content hash and durable artifact references.

Only `source=CAD_BREP` is eligible for authoritative use. The source discriminator is not itself proof of validity: consumers must also verify that the artifact is current, its World Model/design hashes match, and its CAD run succeeded with a valid validation document.

## Authority rules

1. **No CAD, no engineering.** Return the typed `CAD_REQUIRED` result; do not silently fall back to analytical GeometryIR.
2. **No fabricated viewer.** The browser renders a persisted GLB produced by the CAD pipeline. If no GLB is available, explain the missing state and offer CAD generation.
3. **Measurements retain taxonomy.** Values must remain identified as measured, derived from measured geometry, declared by the brief, approximated, or unsupported. Missing inputs remain unknown, not zero.
4. **One dependency chain.** Quantities bind to the geometry artifact/hash. Costs bind to quantity artifacts and the selected rate schedule. Structural and regulatory outputs bind to their canonical inputs. Validation/evidence records the exact dependency hashes.
5. **Staleness is explicit.** A World Model or design change invalidates dependent CAD/engineering artifacts. Stale artifacts remain inspectable as history but cannot be represented as current.
6. **Human review remains mandatory.** Structural outputs are conceptual, regulatory outputs require authoritative rules and evidence, and no result is a certification.

## S4 implementation evidence

- Design alternatives advertise geometry availability only when a CAD B-rep artifact exists.
- The geometry endpoint queries only `CAD_BREP` and returns `CAD_REQUIRED` when the only available artifact is legacy IR.
- The geometry endpoint no longer serializes the `geometry_ir` payload.
- The React viewer loads persisted GLB only; it displays an explicit unavailable/stale state when there is no authoritative model.
- The design workspace exposes a CAD generation action and refreshes geometry/alternative queries after completion.
- Regression tests cover the API's CAD-required behavior and frontend CAD-state mapping.

## Remaining Phase 19 gates

- Migrate every structural, regulatory, validation, evidence, review, and deliverable dependency to canonical CAD-derived artifacts and hash chains.
- Remove remaining legacy GeometryIR execution paths from authoritative code and replace IR-only engine fixtures.
- Prove stale propagation for CAD and all downstream consumers, including races during CAD generation.
- Verify PostgreSQL/PostGIS migrations, real CAD-worker/toolchain integration, tenant isolation, artifact downloads, and full GitHub Actions CI on the final PR head.

## Scope boundary

This contract establishes source authority and traceability. It does not certify geometry correctness for construction, structural adequacy, legal compliance, or cost accuracy.

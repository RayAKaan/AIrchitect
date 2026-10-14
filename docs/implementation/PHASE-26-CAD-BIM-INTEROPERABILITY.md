# Phase 26 — CAD/BIM Exports & Interoperability

**Status:** Delivered; PR #8 merged to `main` (merge commit `09e40a76991b6ebf4f0b466bf93ac5b95c684ca2`).
**Base:** `main` after Phase 25 PR #7 merged.

## Objective

Make existing CAD-worker outputs reviewable and safely downloadable through a canonical, version-bound export manifest. A generated file is not considered an interoperable deliverable merely because a worker wrote bytes to disk.

## Repository-grounded baseline

- The isolated CAD worker already emits GLB, STEP, IFC, FreeCAD document, and B-rep artifacts.
- CAD artifacts are stored content-addressed, with SHA-256, byte size, content type, kind, media role, and run/version scope persisted in PostgreSQL.
- Tenant-scoped download endpoints already exist and hide cross-tenant identifiers.
- Phase 24/25 added the semantic World Model and designer-controlled edits, but its feature-intent specification is not a native CAD export.
- The API must continue to avoid importing FreeCAD, OCCT, or IfcOpenShell; the native toolchain remains isolated in the worker.

## Work packages

1. **Format-level validation:** Verify SHA-256 and byte size against persisted metadata. Check GLB v2 headers/chunk boundaries/JSON asset version, STEP envelope and sections, IFC envelope and recognized schema, and FreeCAD ZIP/Document.xml integrity. B-rep files receive integrity checks but retain a warning because native topology validation belongs to the isolated CAD worker.
2. **Canonical export manifest:** Add a tenant- and version-scoped manifest endpoint. Bind every artifact to its CAD run, source World Model hash, revision ID, and persisted metadata. Report missing/corrupt bytes, failed runs, unsupported formats, review warnings, and stale outputs explicitly.
3. **Fail-closed download affordance:** Only artifacts that pass format/integrity checks and are bound to the current World Model are marked exportable. Stale artifacts remain inspectable but cannot be downloaded from the validated-export UI.
4. **Workspace integration:** Add a CAD/BIM Exports tab to the existing Foundation workspace. Show manifest state, source hash, artifact kind, size, digest, failed/warning checks, and authenticated downloads.
5. **Regression and release evidence:** Add deterministic validator unit tests; add the phase plan/report and tracker entry; make release preflight require Phase 26 documentation; run the existing full CI matrix.

## Acceptance criteria

- [x] No CAD-native library is imported into the API process by the new validation module.
- [x] Export bytes are verified against stored SHA-256 and size metadata.
- [x] GLB, STEP, IFC, and FreeCAD container structure are checked without pretending that structural checks are full round-trip certification.
- [x] B-rep validation is explicitly review-required until checked by the native kernel.
- [x] The manifest is scoped to the authorized project/version and a run from that same scope.
- [x] Stale, failed, missing, corrupt, and review-required artifacts are never marked exportable.
- [x] The Foundation workspace exposes the manifest and authenticated downloads.
- [x] Unit tests, backend Ruff/pytest, PostgreSQL migration cycle, frontend lint/tests/build, Docker builds, Compose readiness/smoke, licence policy, requirements benchmark, and release preflight pass.

## Explicit boundaries and release gates

- Byte/signature checks are not full schema validation or proof of round-trip compatibility in every target application.
- A passing manifest does not certify architectural correctness, structural adequacy, code/zoning compliance, fire/life safety, or constructability.
- Real CAD-host smoke evidence, complete redistribution/source-material notices, and qualified legal sign-off remain Phase 22 release gates.
- No missing dimensions or semantic components are invented to make an export appear complete.

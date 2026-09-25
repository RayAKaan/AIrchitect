# Phase 9 — 3D Viewer (partial)

## Delivered
- React `GeometryViewer` component integrated into the authenticated project list.
- User can open a project workspace and submit bounded dimensions/floor inputs to the authenticated `/geometry/generate` endpoint.
- Displays the actual indexed vertices/faces returned by the API on an interactive canvas (drag to orbit, wheel/controls to zoom, reset view).
- Switches between generated alternatives and shows artifact ID, source revision, area/volume/height, SHA-256, and explicit non-evaluation of compliance/engineering approval.
- Displays API caveats and error/loading states; no fabricated model is shown before generation.
- Responsive viewer layout and project close control.

## Verification
- API test suite: `27 passed`; 4 existing FastAPI lifecycle deprecation warnings.
- Frontend production build was not run: `apps/web/node_modules` is absent in the environment. Install dependencies and run `npm run build` before merge/release.

## Known limitations / remaining gates
- Canvas mesh viewer is a lightweight custom renderer, not Three.js/WebGL; lighting/materials, true 3D picking, robust normals, and camera-fit remain future work.
- Geometry artifacts are generated on demand and are not persisted. The UI asks for source revision; it is not yet bound to or verified against the current World Model revision.
- The floor-guide toggle is reserved UI; current cuboid artifact has only base/top vertices, so individual floor plates are not generated/rendered.
- No browser automation/screenshot test, artifact authorization retrieval endpoint, or multi-project browser integration test.
- Regulatory compliance and engineering approval are always displayed as not evaluated.

## Status
Partial. Do not treat this viewer as a BIM viewer, code-compliance result, or engineering approval.

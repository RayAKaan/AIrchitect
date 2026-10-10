# AIrchitect CAD/BIM Third-Party Notices

**Status: engineering inventory; not yet a commercial redistribution notice.**

AIrchitect's CAD/BIM pipeline uses an isolated worker process. The API container does not directly import FreeCAD, OCCT, or IfcOpenShell. The exact worker environment and native binaries are deployment-specific and must be inventoried from the artifacts actually shipped.

## Reviewed CAD/BIM components

| Component | Recorded version | Recorded licence | Role | Official licence/source |
|---|---:|---|---|---|
| FreeCAD | 1.1.3 | LGPL-2.0-or-later | Separate native CAD process; native document/solid operations | https://github.com/FreeCAD/FreeCAD/blob/1.1.3/LICENSE |
| Open CASCADE Technology (bundled with FreeCAD) | 7.8.1 | LGPL-2.1-or-later with Open CASCADE exception | B-rep geometry kernel | https://github.com/Open-Cascade-SAS/OCCT |
| IfcOpenShell | 0.8.5 | LGPL-3.0-or-later | IFC read/write and BIM exchange | https://github.com/IfcOpenShell/IfcOpenShell |
| cadquery-ocp | 7.9.3.1.1 | Apache-2.0 as recorded in the installed distribution metadata | Python bindings to OCCT | https://github.com/CadQuery/OCP |

The committed machine-generated inventory is `apps/api/app/domains/cad/toolchain_manifest.json`. It records package versions, observed licence metadata, licence files reported by installed distributions, and detected copyleft markers. Regenerate it from the actual target toolchain before changing versions or producing a redistributable bundle.

## Obligations and release controls

- Preserve each component's applicable licence and copyright notices.
- For any redistribution, include the complete licence texts and any applicable source offer/source pointers required by the component's licence. A URL in this document is not a substitute for shipping required licence materials.
- Preserve the exact Open CASCADE exception text applicable to the distributed OCCT build.
- Audit all transitive packages and every library bundled inside the FreeCAD archive; do not infer that a package is permissively licensed merely because its metadata is incomplete.
- Re-run the manifest policy check after changing the worker environment or native binaries.
- Obtain qualified legal review of the distribution and process-isolation model before commercial redistribution.

## Current release status

Commercial redistribution is **not cleared** by this inventory. The FreeCAD archive recorded by the existing audit does not contain a root licence file, several transitive package licence identifiers are unresolved in the committed manifest, and the existing audit explicitly requires legal countersignature. The policy gate permits the reviewed LGPL components for ordinary development/CI but keeps release approval false until these items are resolved.

See `docs/legal/PHASE-18-OPEN-SOURCE-LICENSE-AUDIT.md` and `docs/legal/cad-license-policy.json`.

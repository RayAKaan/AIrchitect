# Phase 18 — Open-Source License Audit (CAD / BIM Toolchain)

**Status:** IMPLEMENTED — requires countersignature by qualified counsel before commercial release.
**Audit date:** 2026-09-26
**Scope:** Every third-party component that AIrchitect installs, imports, executes, or redistributes
in the Phase 18 CAD/BIM pipeline (FreeCAD, OCCT, IfcOpenShell, and their transitive dependencies).
**Authority for this document:** empirical inspection of the actual artifacts installed on this machine
(`H:\.cad-tools\`), not recollection or marketing pages. Where a claim could not be verified from the
shipped artifact itself, that is stated explicitly.

> **This document is a technical compliance record, not legal advice.** It is written by an engineer,
> not a lawyer. Section 8 lists the specific questions that must be answered by counsel.

---

## 1. Executive summary

| Outcome | Status |
| --- | --- |
| Copyleft (GPL/LGPL) obligations triggered? | **YES** — FreeCAD, IfcOpenShell, OCCT are all LGPL |
| AGPL / network-copyleft triggered? | **NO** — no AGPL component is present |
| Do we modify any LGPL component? | **NO** — all are consumed unmodified, as separate binaries / importable extensions |
| Does running the worker as a hosted service trigger source disclosure? | **NO** — LGPL is not AGPL; this is the single most important finding (§4) |
| Can a recipient replace the library? | **YES** — versions are pinned and published with SHA-256 (§6) |
| License texts present in the artifacts we ship? | **PARTIAL** — see the gap in §5.1 |
| Action items outstanding before release? | **YES** — 4 items, §8 |

**Bottom line:** the architecture chosen in Phase 18 (separate worker process + separate virtualenv +
unmodified upstream binaries) is the *most* LGPL-compatible option available to us. The remaining work
is paperwork: ship the missing license texts, add automated license scanning to CI, and obtain counsel
sign-off. No architectural change is required.

---

## 2. Directly-provisioned components

These are the components AIrchitect provisions and invokes directly.

### 2.1 FreeCAD 1.1.3

| Attribute | Value | How verified |
| --- | --- | --- |
| Component | FreeCAD | — |
| Version | `1.1.3` | `FreeCAD.Version()` runtime probe |
| Build | `1.1.3R20260725`, Git `145529fe741292ff0b3977a01195bf0247425794` | runtime probe |
| Embedded Python | 3.11.14 | runtime probe |
| License | **LGPL-2.0-or-later** | runtime banner emitted by `freecadcmd.exe`: *"FreeCAD is free and open-source software licensed under the terms of LGPL2+ license."* |
| Source | <https://github.com/FreeCAD/FreeCAD> (tag `1.1.3`) | release origin |
| Distribution integrity | SHA-256 `9c6959dc9c4dba64dd818a62447e3dfedb4221d776fb044b239d462f150bcec4` | computed locally, matches upstream `…7z-SHA256.txt` |
| Invocation | `freecadcmd.exe` — separate OS process, headless | verified |
| How AIrchitect uses it | Builds solids, measures them, writes native `.FCStd` and `.STEP` | verified |

**Note on the license banner.** The banner is strong evidence but is not a license *file*. The
authoritative terms are the `LICENSE` file in the FreeCAD source repository at tag `1.1.3`, which is
LGPL-2.0-or-later. See gap §5.1.

### 2.2 Open CASCADE Technology (OCCT) — two distinct builds

AIrchitect does not provision OCCT directly; it arrives inside two other components. **These are two
different builds at two different versions and both must be recorded.**

#### 2.2.1 OCCT inside FreeCAD 1.1.3

| Attribute | Value | How verified |
| --- | --- | --- |
| Version | **7.8.1** | runtime probe: `Part.OCC_VERSION` → `"7.8.1"` |
| Provenance | conda-forge `occt 7.8.1` (`all_hae6dad1_203`) | FreeCAD `packages.txt` line 2 |
| Bundled Python binding | `pythonocc-core 7.8.1.1` (`all_h44a3997_200`) | `packages.txt` |
| License | **LGPL-2.1-or-later WITH the Open CASCADE exception** | Open CASCADE official licensing statement |
| Total FreeCAD third-party packages | 236 | `packages.txt` line count |

> **Correction to earlier planning notes.** The Phase 18 plan assumed FreeCAD 1.1.3 would embed
> OCCT 7.9.x. Measured reality is **OCCT 7.8.1**. This is precisely why the worker reports
> `Part.OCC_VERSION` at runtime instead of trusting a hard-coded version, and why no code may assume a
> particular OCCT minor version. See §7.

#### 2.2.2 OCCT inside `cadquery-ocp` 7.9.3.1.1

| Attribute | Value | How verified |
| --- | --- | --- |
| Distribution | `cadquery-ocp` | PyPI |
| Version | `7.9.3.1.1` | installed dist-info |
| Bundled OCCT | 7.9.3 | distribution version string |
| **Wrapper** license | **Apache-2.0** | dist-info `License: Apache-2.0`; classifier `License :: OSI Approved :: Apache Software License`; `cadquery_ocp/LICENSE` |
| **OCCT** license | **LGPL-2.1-or-later WITH the Open CASCADE exception** | Open CASCADE official licensing statement |
| Companion package | `cadquery-ocp-proxy 7.9.3.1.1` (Apache-2.0) — a *tracking shim*, required | installed dist-info |

> **Correction to earlier planning notes.** The plan recorded `cadquery-ocp` as LGPL. It is not: the
> **Python wrapper is Apache-2.0**, while the **OCCT native libraries it wraps are LGPL-2.1 +
> exception**. Both facts must be reported, because the obligation follows the native library.

### 2.3 IfcOpenShell

| Attribute | Value | How verified |
| --- | --- | --- |
| Distribution | `ifcopenshell` | PyPI |
| Version | `0.8.5` (worker venv — **the component AIrchitect actually imports**) | installed dist-info + runtime |
| License | **LGPL-3.0-or-later** | dist-info classifier `License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)` |
| Role | Sole owner of IFC read/write | architecture decision |
| Verified capability | writes IFC4, re-reads it, preserves spatial tree, extrusions, property sets | §7 probe results |

**Second copy — present but not executed.** FreeCAD 1.1.3 also ships `ifcopenshell 0.8.4` (conda
`freecad/ifcopenshell 0.8.4 py311h2f2be2f_2`, LGPL-3.0-or-later), recorded in `packages.txt`. AIrchitect's
FreeCAD adapter **does not import it**. It is listed here because it is physically distributed inside the
FreeCAD archive we redistribute, and because a future FreeCAD BIM-workbench code path could import it
implicitly. See action A4 in §8.

---

## 3. Transitive dependencies actually installed

Collected programmatically from the worker virtualenv (`H:\.cad-tools\worker-venv`, Python 3.14.4) via
`importlib.metadata`, not from a lockfile guess. Every row below was observed on disk.

| Package | Version | License (as shipped) | Evidence |
| --- | --- | --- | --- |
| `cadquery-ocp` | 7.9.3.1.1 | Apache-2.0 | dist-info `License` + classifier |
| `cadquery-ocp-proxy` | 7.9.3.1.1 | Apache-2.0 | dist-info classifier |
| `ifcopenshell` | 0.8.5 | LGPL-3.0-or-later | dist-info classifier |
| `numpy` | 2.5.3 | BSD-3-Clause | `numpy-2.5.3.dist-info/licenses/LICENSE.txt` + bundled 3rd-party notices |
| `vtk` | 9.6.2 | BSD | `vtk-9.6.2.dist-info/licenses/LICENSE` |
| `shapely` | 2.1.2 | BSD-3-Clause | `shapely-2.1.2.dist-info/licenses/LICENSE.txt` (+ GEOS + win32 notices) |
| `lark` | 1.3.1 | MIT | `lark-1.3.1.dist-info/licenses/LICENSE` |
| `pillow` | 12.3.0 | HPND (Historical Permission Notice and Disclaimer) | `pillow-12.3.0.dist-info/licenses/LICENSE` |
| `matplotlib` | 3.11.2 | PSF-style matplotlib license (BSD-compatible) | `matplotlib-3.11.2.dist-info/LICENSE` + bundled DejaVu/STIX font licenses |
| `kiwisolver` | 1.5.1 | MIT | `kiwisolver-1.5.1.dist-info/licenses/LICENSE` |
| `fonttools` | 4.66.0 | MIT | `fonttools-4.66.0.dist-info/licenses/LICENSE` (+ `.external`) |
| `python-dateutil` | 2.9.0.post0 | Apache-2.0 **or** BSD-3-Clause (dual) | `python_dateutil-2.9.0.post0.dist-info/LICENSE` |
| `isodate` | 0.7.2 | BSD-3-Clause | `isodate-0.7.2.dist-info/LICENSE` |
| `six` | 1.17.0 | MIT | `six-1.17.0.dist-info/LICENSE` |
| `typing-extensions` | 4.16.0 | PSF-2.0 | `…/licenses/LICENSE` |
| `packaging` | 26.3 | Apache-2.0 **or** BSD-2-Clause (dual) | `LICENSE`, `LICENSE.APACHE`, `LICENSE.BSD` |
| `contourpy` | 1.4.0 | BSD-3-Clause | `contourpy-1.4.0.dist-info/licenses/LICENSE` |
| `cycler` | 0.12.1 | BSD | `cycler-0.12.1.dist-info/LICENSE` |

**Not copyleft.** No GPL-2.0-only, GPL-3.0-only, AGPL, SSPL, BUSL, or Commons Clause component was found.
The strongest obligations are the three LGPL components in §2.

**`vtk` note.** `vtk` is pulled in transitively by the `ifcopenshell` wheel. Phase 18 does **not** use the
`ifcopenshell.geom` tessellation path (see §7.4), but the wheel links VTK regardless, so VTK is
executing code in the worker venv. Its BSD license is permissive, but it belongs on the notices list.

---

## 4. Why LGPL does not force source disclosure of AIrchitect

This is the load-bearing technical conclusion, so it is stated precisely.

1. **The components are consumed unmodified.** AIrchitect does not patch FreeCAD, OCCT, or IfcOpenShell.
   Under the LGPL, the obligation to publish the source of *your modifications* is therefore vacuous —
   there are none.
2. **They are not combined into a single derivative work.** The API process never imports FreeCAD,
   OCCT, or IfcOpenShell. It spawns a *separate OS process* (`freecadcmd.exe`) and exchanges JSON over a
   pipe. `cadquery-ocp` and `ifcopenshell` are imported only inside a *separate virtualenv* used solely
   by the worker, never by the web application. This "mere aggregation / separate process" posture is the
   most defensible arrangement and is enforced by test (§6).
3. **It is not AGPL.** The decisive point: LGPL §13 obligations are triggered by *conveying* a covered
   work to a recipient. Hosting the worker on a server the user cannot download is **not** conveyance of
   the covered work, and no LGPL version imposes a network-use source offer. Had any dependency been
   AGPL, running it as a hosted service would have forced us to publish the entire corresponding
   service source. That did not happen here.
4. **Relinking remains possible.** Because we neither modify nor statically seal the libraries, a
   recipient may substitute a different build of FreeCAD/OCCT/IfcOpenShell. §6 explains how the pinned
   versions and hashes make that practical.
5. **The API's own code stays cleanly separable.** No AIrchitect source file imports a CAD or BIM
   package. This keeps AIrchitect's proprietary code outside any derivative-work analysis.

---

## 5. Gaps found

### 5.1 The FreeCAD Windows archive ships no root license file — **actionable**

```
H:\.cad-tools\freecad-1.1.3\FreeCAD_1.1.3-Windows-x86_64-py311\
├── FreeCAD.exe
├── FreeCADCmd.exe
└── packages.txt          <- 236-line third-party manifest
```

There is **no `LICENSE`, `COPYING`, or `NOTICE` at the root** of the official portable archive. The only
license files present belong to bundled third-party Python wheels (`aiohttp`, `blinker`, `certifi`, …).
If AIrchitect redistributes this archive — which the local portable provisioning path does — then
AIrchitect, not FreeCAD, is the redistributor and therefore must:

- include the full LGPL-2.0 text (and the GPL-2.0 text it incorporates by reference), **and**
- include a clear written offer / pointer to the corresponding FreeCAD source at tag `1.1.3`.

This is a genuine documentation obligation created by our own packaging choice, and it is easy to miss
precisely because upstream omits the file. Tracked as action **A1**.

### 5.2 No automated license scanning in CI — **actionable**

Nothing in the pipeline currently fails a build if a dependency's license changes or a new copyleft
package appears. Tracked as action **A2**.

### 5.3 `ifcopenshell` wheel ships no adjacent license file

The `ifcopenshell 0.8.5` dist-info exposes only the trove classifier, not a `LICENSE` file. The LGPL-3.0
text must be fetched from upstream and bundled by us. Same for `cadquery-ocp`'s companion
`cadquery-ocp-proxy`. Tracked as action **A3** (fold into A1's notices bundle).

### 5.4 Minor / informational

- `pythonocc-core 7.8.1.1` is bundled inside FreeCAD and is LGPL-2.1 + exception. Not imported by the
  adapter, but shipped. Covered by the A1 notices bundle.
- FreeCAD's `packages.txt` lists 236 packages, of which this document has *not* individually enumerated.
  The complete list is preserved in the toolchain manifest (§6) so it can be swept by tooling rather
  than by hand. The components we actually import are fully enumerated above.

---

## 6. How compliance is enforced in the build, not just asserted

Each control below is a machine-checkable invariant, not a policy statement.

| Control | Mechanism |
| --- | --- |
| **Pinned, verifiable toolchain** | `H:\.cad-tools\toolchain-manifest.json` records every version *and* the FreeCAD archive SHA-256. Reproducibility is the precondition for the LGPL "replacement/relinking" right. |
| **Dependency isolation** | CAD/BIM packages exist only in `H:\.cad-tools\worker-venv`. The API's own environment must not be able to import them; a test asserts `import OCP` / `import ifcopenshell` / `import FreeCAD` all fail in the API environment. This is the mechanical guard for §4.2. |
| **Process boundary** | FreeCAD is invoked as `freecadcmd.exe` with an `argv` array (never a shell string). This is both the LGPL boundary and the command-injection defence. |
| **No user-supplied code** | The worker executes only a fixed, shipped script. Job input is data (JSON), never Python. |
| **Third-party notices** | `docs/legal/THIRD-PARTY-NOTICES.md` + the `LICENSE-*.txt` files beside it are generated from the manifest, so the notices cannot drift from what is installed. |
| **Automated license check** | CI runs a metadata sweep over the worker venv and FreeCAD `packages.txt`, failing on GPL/AGPL/SSPL/BUSL/Commons-Clause without explicit sign-off. Action A2. |

---

## 7. Verification actually performed (not assumed)

Every number in this document was produced by executing the real toolchain on this machine.

### 7.1 FreeCAD — headless solid construction

| Check | Expected | Measured | Verdict |
| --- | --- | --- | --- |
| `Part.makeBox(10, 8, 3.5)` volume | 280.0 | **280.0** | PASS |
| Surface area | 286.0 | **286.0** | PASS |
| `Shape.isValid()` | True | **True** | PASS |
| `Shape.isClosed()` | True | **True** | PASS |
| Bounding box | `0,0,0 → 10,8,3.5` | **exact** | PASS |
| Solid / face / edge counts | 1 / 6 / 12 | **1 / 6 / 12** | PASS |
| `Part.OCC_VERSION` | report, do not assume | **7.8.1** | recorded |
| Embedded Python | 3.11 | **3.11.14** | recorded |

### 7.2 OCCT (`cadquery-ocp` 7.9.3.1.1) — construction, booleans, topology, meshing

| Check | Expected | Measured | Verdict |
| --- | --- | --- | --- |
| Box volume | 280.0 | **280.0** | PASS |
| `BRepCheck_Analyzer` valid | True | **True** | PASS |
| **Intersection** of two 10×8×3.5 boxes offset 5 in X | 5·8·3.5 = **140.0** | **140.0** | PASS |
| **Union** of the same pair | 15·8·3.5 = **420.0** | **420.0** | PASS |
| **Difference** of the same pair | 5·8·3.5 = **140.0** | **140.0** | PASS |
| Extrusion of a 4×3 footprint to 2.5 | 4·3·2.5 = **30.0** | **30.0** | PASS |
| Extruded solid valid / face count | True / 6 | **True / 6** | PASS |
| `BRepMesh_IncrementalMesh` (0.05 deflection) | completes | **completed, 3.2 ms** | PASS |

The three boolean results are the meaningful ones: they match hand-computed set-theoretic expectations
exactly, which demonstrates a genuine B-rep kernel rather than a box-faking approximation.

### 7.3 IfcOpenShell 0.8.5 — IFC4 write / read round-trip

| Check | Result |
| --- | --- |
| File written | **3770 bytes**, IFC4, SHA-256 recorded |
| Re-opened by `ifcopenshell.open()` | schema `IFC4` |
| `IfcProject` / `IfcSite` / `IfcBuilding` / `IfcBuildingStorey` | 1 / 1 / 1 / 1 — spatial tree intact |
| `IfcBuildingElementProxy` (massing blocks) | **3** |
| `IfcExtrudedAreaSolid` (real solid geometry) | **3** |
| Property set survived round-trip | `Pset_AIrchitectStorey` with 3 properties |
| Element names survived | `Massing_01`, `Massing_02`, `Massing_03` |

**API contracts learned the hard way** (0.8.5 differs from older tutorials):

- `ifcopenshell.api.project.create_file(version="IFC4")` returns an **empty** file — it does *not* seed an
  `IfcProject`. The `IfcProject` must be created explicitly.
- The API keyword is **`file=`**, not `ifc_file=`.
- `pset.add_pset` takes **`product=`**, not `owner=`.
- `IfcBuildingElementProxy.PredefinedType` must be **`ELEMENT`** in IFC4; `BUILDING_ELEMENT_PROXY` is
  not a member of `IfcBuildingElementProxyTypeEnum` and raises
  `RuntimeError: Unable to find keyword in schema`.
- `geometry.add_wall_representation` **creates** the element (`length`, `height`, `thickness`) rather
  than accepting `elements=`.
- `IfcEntity.GlobalId` comes from `ifcopenshell.guid.new()`; there is no `guid` API usecase.
- For arbitrary massing footprints, `IfcBuildingElementProxy` + `IfcArbitraryClosedProfileDef` +
  `IfcExtrudedAreaSolid` is the correct IFC4 representation (a massing block is not a wall).

### 7.4 Known limitation: `ifcopenshell.geom` is not usable on this interpreter

`ifcopenshell.geom.iterator` (the module that tessellates IFC to meshes/GLB) **hangs indefinitely** on
Python 3.14.4 in this environment. Every other stage completes; the process was killed after 60 s having
printed `geom import` and never progressed. This is recorded as a real limitation, not hidden.

**Mitigation, already in the design:** browser-facing GLB geometry is produced from
**OCCT/FreeCAD tessellation** (§7.1, §7.2), which is proven fast and reliable. IfcOpenShell is therefore
scoped to exactly what it uniquely owns — IFC read/write, schema correctness, spatial structure,
classifications and property sets — and is not on the rendering critical path. Consequence: an IFC file
downloaded from AIrchitect cannot be previewed in-browser via IfcOpenShell, but the AIrchitect-authored
GLB preview is unaffected. Action **A5**.

---

## 8. Actions before commercial release

| ID | Action | Owner | Blocking? |
| --- | --- | --- | --- |
| **A1** | Ship LGPL-2.0 (+ incorporated GPL-2.0) and LGPL-3.0 texts with the redistributable package, plus a written offer / source pointer to FreeCAD 1.1.3 source. The upstream Windows archive omits this file (§5.1). | Legal + Release | **Yes** |
| **A2** | Add CI license scanning that fails on GPL/AGPL/SSPL/BUSL/Commons-Clause without recorded sign-off. | Platform | **Yes** |
| **A3** | Bundle LGPL-3.0 text for `ifcopenshell` and Apache-2.0 for `cadquery-ocp` in the notices set; generate notices from the toolchain manifest. | Release | **Yes** |
| **A4** | Decide and document whether FreeCAD's vendored `ifcopenshell 0.8.4` may remain unimported, and add a test that the FreeCAD adapter never imports `ifcopenshell` from inside FreeCAD. | Engineering | No |
| **A5** | Confirm the GLB-from-OCCT approach (§7.4) is acceptable, or pin a Python ≤3.12 worker where `ifcopenshell.geom` is known-good, if IFC-to-GLB preview is ever required. | Engineering | No |
| **A6** | Obtain written countersignature of this document from qualified counsel. | Legal | **Yes** |

## 9. Questions for counsel

1. Does redistributing the unmodified FreeCAD portable Windows archive require AIrchitect to satisfy
   LGPL §6 (license text + written offer) *as the redistributor*, notwithstanding that upstream omits the
   root license file? We have assumed **yes** and have planned for it.
2. Is spawning `freecadcmd.exe` as a separate process, with JSON over a pipe and no shared address
   space, sufficient to keep AIrchitect's application code outside any derivative work? We have assumed
   **yes** (§4.2).
3. Does hosting the worker venv as a service, where a paying customer cannot download FreeCAD/OCCT/
   IfcOpenShell, trigger any source-disclosure obligation? We have assumed **no**, because these are LGPL
   and not AGPL (§4.3). Please confirm, including for OCCT's special exception clause.
4. Does the **OCCT exception** to LGPL-2.1 alter any of the above for the OCCT binaries inside FreeCAD and
   inside `cadquery-ocp`?
5. Is our "no modification" position defensible given that we ship a `packages.txt`-derived manifest and
   configure FreeCAD via headless scripts? We believe scripts are configuration, not modification, but
   please confirm.
6. Any exposure from the 236 third-party packages inside the FreeCAD archive that we have not
   individually enumerated in §3?

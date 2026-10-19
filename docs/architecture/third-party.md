# Third-Party Architecture Policy

Third-party dependencies are part of the product architecture. Selection must consider license, maintenance, security, browser/runtime compatibility, performance and fit with canonical-state boundaries.

## Preferred baseline

MIT, BSD-family, Apache-2.0, ISC, 0BSD and CC0 are preferred where otherwise equivalent.

MPL/LGPL require deliberate linking/redistribution review. GPL/AGPL/SSPL or unknown licensing must not be introduced as a default production dependency without an explicit legal decision and documented replacement strategy.

## Machine-readable compliance registry

`docs/legal/compliance-registry.json` is the canonical engineering registry for reviewed third-party software, provider terms, data sources, attribution requirements and license reviews. Each software record captures name, version, repository, license, copyright, purpose, runtime, linking mode, modification status, data dependencies, commercial restrictions, replacement strategy, classification, owner and review dates.

`REJECTED` is an explicit classification and is not a substitute for deleting a dependency. A rejected dependency must have a documented replacement strategy and must not silently enter a production path.

The registry is validated by `scripts/check_compliance_registry.py`. Review dates are enforced as release invariants. `scripts/generate_third_party_notices.py --check` also ensures the committed `docs/legal/THIRD-PARTY-NOTICES.md` is generated from the registry rather than manually drifting.

## Software and data are separate compliance surfaces

A software license does not establish rights to use a dataset. Provider terms and data sources therefore have separate registry fields for license, terms version/URL, commercial use, caching, attribution, geographic scope and review dates. No provider or dataset is considered approved merely because its SDK or client library is permissively licensed.

The initial S0.3 registry records the empirically reviewed CAD/BIM worker toolchain from Phase 18. It intentionally does **not** claim that the existing web/API dependency graph or future site-data providers have completed license review. New dependencies and data providers must be registered as part of the PR that adopts them.

## Planned evaluation set

The roadmap identifies React, React Three Fiber, Three.js, TanStack Query, Zustand, Radix, resizable panels, Lucide, MapLibre GL JS, MapLibre-Geoman, Turf.js, Shapely, pyproj, selective GeoPandas and React Flow as preferred/open candidates, subject to repository lockfile and license review.

OR-Tools CP-SAT, ThatOpen, web-ifc, IfcOpenShell, PMTiles, CesiumJS, OpenCascade.js, Speckle and Yjs require capability-specific evaluation before adoption.

## Architecture rule

Do not add a dependency solely to make a prototype easier if it creates a second source of truth, a restrictive license problem, unacceptable bundle/runtime cost or an unmaintained critical path.

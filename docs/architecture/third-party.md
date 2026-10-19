# Third-Party Architecture Policy

Third-party dependencies are part of the product architecture. Selection must consider license, maintenance, security, browser/runtime compatibility, performance and fit with canonical-state boundaries.

## Preferred baseline

MIT, BSD-family, Apache-2.0, ISC, 0BSD and CC0 are preferred where otherwise equivalent.

MPL/LGPL require deliberate linking/redistribution review. GPL/AGPL/SSPL or unknown licensing must not be introduced as a default production dependency without an explicit legal decision and documented replacement strategy.

## Planned evaluation set

The roadmap identifies React, React Three Fiber, Three.js, TanStack Query, Zustand, Radix, resizable panels, Lucide, MapLibre GL JS, MapLibre-Geoman, Turf.js, Shapely, pyproj, selective GeoPandas and React Flow as preferred/open candidates, subject to repository lockfile and license review.

OR-Tools CP-SAT, ThatOpen, web-ifc, IfcOpenShell, PMTiles, CesiumJS, OpenCascade.js, Speckle and Yjs require capability-specific evaluation before adoption.

## Architecture rule

Do not add a dependency solely to make a prototype easier if it creates a second source of truth, a restrictive license problem, unacceptable bundle/runtime cost or an unmaintained critical path.

## Current repository state

The repository already has a substantial frontend/backend dependency set. S0.3 will make dependency licensing machine-readable and connect it to release preflight. This document intentionally does not claim every current dependency has already passed that review.

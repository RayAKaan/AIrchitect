# S1 Completion Contract

**Stage:** S1 — Site World Model / Site Workspace  
**Status:** Complete

## Canonical state

- [x] Site and site-revision persistence
- [x] Revision hashes and parent lineage
- [x] Validated `SetSiteBoundary` command
- [x] Idempotency and stale-base protection
- [x] Server-authoritative canonical persistence
- [x] EPSG:4326 interchange and site-local metric calculation CRS

## Boundary workflows

- [x] Manual/map boundary editing
- [x] GeoJSON Polygon import/export
- [x] KML single-Polygon import/export
- [x] Fail-closed geometry validation
- [x] Imported geometry remains a local draft until server commit

## Provider/context layer

- [x] Provider capability catalog
- [x] Reviewed terms and health state
- [x] Commercial-use and caching gates
- [x] HTTPS endpoint validation
- [x] Response-size/content-type/schema validation
- [x] Persisted source and dataset lineage
- [x] Context snapshots tied to site revision

## Site analysis

- [x] Deterministic context intersection metrics
- [x] Road hierarchy, frontage and mobility counts
- [x] Land-use counts
- [x] Green/water metrics
- [x] Figure-ground/building coverage metrics
- [x] Solar boundary orientation
- [x] Explicit climate/terrain `UNKNOWN` state without an authoritative provider
- [x] Deterministic runner version and source-context hash

## Evidence and freshness

- [x] Source/date/dataset/version/scope/method/confidence/status/revision lineage
- [x] Current versus historical evidence visibility
- [x] Historical derived rows materialized as `STALE` on new site revisions
- [x] Server-authoritative freshness endpoint
- [x] No client timestamp or heuristic determines freshness

## Diagrams and presentation

- [x] Figure-ground
- [x] Movement/access
- [x] Land use
- [x] Green/water
- [x] Solar/orientation
- [x] Deterministic SVG output
- [x] Analysis/freshness readiness gate
- [x] Presentation-only board composition
- [x] Stale-data export gating
- [x] A1/A2/A3/16:9 sheet support

## UX and acceptance

- [x] Site Workspace shell
- [x] Layer controls with stable IDs
- [x] Loading/error/retry states
- [x] Keyboard and screen-reader semantics for core controls
- [x] Onboarding templates
- [x] Authenticated browser acceptance for site and board workflow
- [x] Deterministic backend acceptance tests for geometry, analysis and diagrams

## Explicit non-goals

S1 does not claim completion of:

- architectural program generation;
- envelope/setback/FAR design generation;
- concept alternatives;
- universal architectural commands;
- semantic building modeling;
- 3D/2D unified editing;
- drawing compilation;
- full architectural analysis;
- IFC/CAD round-trip;
- collaboration or AI Copilot.

Those capabilities begin in S2 and later stages.

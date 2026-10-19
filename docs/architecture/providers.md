# Provider Architecture

External services are adapters, not domain authorities. Provider-specific logic must not leak into canonical domain models.

## Provider capabilities

The roadmap identifies these capability classes:

- geocoding;
- basemap/context;
- terrain/DEM;
- climate/weather;
- planning/regulatory data;
- imagery;
- storage;
- AI inference;
- CAD processing;
- IFC processing;
- PDF/rendering.

## Provider record

A future provider registry should identify provider, capability, coverage, health and terms. Provider terms must be versioned and include license, attribution, rate limits, commercial-use restrictions and caching permissions.

## Fetch lineage

Provider-backed data must record provider identity, capability/dataset, dataset version where available, retrieval time, geographic scope, source reference and applicable data terms. Normalized values become project evidence only through an explicit ingestion path.

## Current repository state

The repository contains domain-specific integrations and evidence/provenance support, but does not yet have one universal provider adapter registry and terms service. The S1 provider layer must consolidate this capability without forcing domain code to depend on vendor SDKs.

## Failure policy

Provider failures are explicit product states. A timeout, unavailable dataset, coverage gap or terms restriction must not silently become a fabricated value. The domain may return `UNKNOWN`, `STALE` or a provider-specific error that the UI can explain.

## Caching

Caching is capability-specific and terms-dependent. A cache must retain provider/dataset/version lineage and respect the provider's terms. Cache keys for deterministic site analysis should include the canonical site revision hash, provider dataset/version and analysis runner version.

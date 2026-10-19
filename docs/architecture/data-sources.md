# Data Sources and Terms

Software licenses and data licenses are separate concerns. A technically usable dataset is not automatically commercially usable.

## Source classes

| Class | Examples | Current status |
|---|---|---|
| User-provided | briefs, uploaded site files, project decisions | supported in existing workflows |
| Internal canonical | project/version/World Model/artifact records | authoritative |
| Provider-derived | geocoding, map/context, terrain, climate, planning | adapters/registry are roadmap work |
| Generated | diagrams, drawings, meshes, analyses, boards | derived; must retain lineage |
| AI-derived | extracted/proposed facts | proposal/interpretation until validated |

## Required source metadata

Where a source contributes factual project state, retain as applicable:

- source/provider name and identifier;
- dataset name and version;
- source URL/reference;
- retrieval/acquisition time;
- geographic scope and resolution;
- source CRS/units;
- license and data-use terms;
- attribution requirements;
- raw artifact/reference and hash where feasible;
- transformation/normalization method;
- owning project/revision.

## Unknown and stale data

Missing source evidence must remain `UNKNOWN`. A previously valid provider result becomes `STALE` when the provider dataset, project revision or applicability changes according to the source contract.

## Public map/context data

The roadmap permits an initial OSM-derived context layer, but the implementation must use a provider/data adapter with explicit attribution and terms handling. It must not hard-code a public tile URL as if it were a universal production service.

## Current repository state

The current repository has evidence/provenance records and source fields across multiple domains. It does not yet have the universal data-source registry. S0.3 will implement that registry and release checks; S1 will consume it for site providers.

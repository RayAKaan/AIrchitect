# AIrchitect Benchmark Corpus

S0.6 establishes a versioned, deterministic benchmark corpus for regression testing architectural interpretation and downstream generation. The corpus is intentionally a **benchmark specification**, not a claim that AIrchitect can already solve every case end-to-end.

## Corpus layout

- `manifest.json` — corpus version, coverage matrix, case index, and expected benchmark dimensions.
- `briefs/` — 20 structured architectural briefs covering student, residential, retail, hospitality, office, mixed-use, institutional and Saudi-context work.
- `sites/` — 10 site/context cases with boundary geometry, CRS expectations, evidence expectations and site-analysis outcomes.
- `concepts/` — deterministic concept expectations for alternative generation and metric traceability.
- `layouts/` — canonical semantic-layout expectations for downstream building-model tests.
- `regeneration/` — dependency-aware change scenarios used to verify stale propagation and recomputation.
- `boards/` — presentation-board expectations and stale-data behavior.

## Benchmark principles

1. Inputs are versioned and machine-readable.
2. Expected outcomes distinguish hard requirements from qualitative guidance.
3. Unknown regulatory/environmental facts remain `UNKNOWN`; the corpus never licenses fabricated certainty.
4. Site cases use WGS84 (`EPSG:4326`) for interchange and specify a site-local projected metric CRS for authoritative calculations.
5. Deterministic cases specify reproducibility expectations, not a single implementation-specific rendering.
6. Benchmarks are regression fixtures. They are not universal claims about architectural competence or NLP accuracy.
7. Saudi cases identify jurisdiction/context explicitly so providers and planning rules can be evaluated against evidence rather than inferred from location alone.

## Validation

Run from the repository root:

```bash
python scripts/validate_benchmark_corpus.py
```

The validator checks manifest integrity, required coverage, unique case IDs, schema-level fields, geometry basics, expected-outcome structure, and cross-references. CI must fail if the corpus is malformed or incomplete.

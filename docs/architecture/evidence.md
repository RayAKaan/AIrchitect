# Evidence and Provenance

Evidence is a first-class input to professional architectural decision support. A factual claim must not be presented as verified merely because a model generated it.

## Required lineage

The canonical evidence chain is:

`VALUE → SOURCE → DATE → DATASET/VERSION → GEOGRAPHIC SCOPE → METHOD → CONFIDENCE → STATUS → REVISION`

Where applicable, evidence records should also preserve provider, retrieval time, URL/reference, attribution, license/data terms, resolution, raw source reference, normalized value and the runner/transform version.

## Status values

- `VERIFIED` — authoritative evidence supports the value for the stated scope/date.
- `SUPPORTED` — a credible source supports the value, but the evidence is not sufficient for verification.
- `UNKNOWN` — no adequate evidence is available.
- `CONFLICTING` — credible sources disagree or applicability cannot be reconciled.
- `STALE` — the evidence was valid for an earlier revision/date but is no longer current.

`UNKNOWN` is a valid product state. It must not be replaced with a plausible value.

## Inheritance

Derived facts inherit the weakest relevant evidence status. An AI-extracted value cannot become `VERIFIED` solely because an LLM produced it. Superseded evidence becomes `STALE` when its source/revision is no longer current.

## AI boundary

AI may extract, summarize, classify or propose a fact. The evidence service owns provenance and status. The UI must distinguish AI interpretation from source-backed fact.

## Current repository state

The repository already has an `evidence` domain and provenance fields on several records, including requirements and artifact versions. The evidence model is not yet the universal evidence contract described here. S0 establishes the contract so later Site/Planning/Provider implementations converge on one pattern rather than adding incompatible evidence payloads.

## Minimum provider-backed evidence

Provider-backed facts should retain:

- provider identifier;
- capability/dataset;
- dataset/provider version when available;
- retrieval timestamp;
- geographic scope;
- source reference/URL;
- terms/license and attribution requirement;
- raw reference or artifact hash;
- normalized value;
- confidence and status;
- owning canonical revision.

## Professional boundary

Evidence-backed feasibility support is not a professional certification. Regulatory, structural, fire, accessibility and other compliance claims require authoritative jurisdiction-specific evidence and appropriate human/professional review.

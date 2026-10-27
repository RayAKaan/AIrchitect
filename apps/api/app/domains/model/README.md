# Canonical architectural model

This package defines AIrchitect's authoritative parametric building state.

## Boundary

- LLMs and UI produce proposals or commands; they do not own model state.
- Model instances are immutable-in-use Pydantic values.
- Mutations belong to the command layer introduced in later S10 slices.
- Geometry and downstream artifacts must be derived from this model.
- `model_hash()` provides deterministic identity for provenance and revision checks.

## Initial object vocabulary

`Site`, `Building`, `Level`, `Space`, `Wall`, `Door`, `Window`, `Slab`, and `Stair` are intentionally small, explicit primitives. Future phases may extend the vocabulary without changing the ownership rule: the canonical model remains the source of truth.

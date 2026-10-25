# S3 — Universal Command Contract

Status: implemented as the contract layer.

The command envelope is the convergence point for direct editing, AI proposals, previews, commits and regeneration. This slice intentionally does not mutate canonical state. Unknown command types fail closed, schema versions are explicit, and preview mode is non-mutating by contract.

## Next slices

1. persistence/idempotency
2. adapters for existing site and semantic mutations
3. impact preview and dependency propagation
4. history/restore
5. intent proposal
6. authenticated browser acceptance

Canonical state remains server-owned; existing mutation services remain authoritative until each adapter is migrated.

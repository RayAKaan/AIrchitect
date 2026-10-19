# Dependency and Regeneration Architecture

## Authority

The Phase 27 artifact dependency graph is authoritative for causal relationships between versioned artifacts. New dependency systems must extend it rather than create parallel graphs.

## Current graph

`ArtifactVersion` stores versioned derived artifacts. `ArtifactDependency` stores directed dependency edges between artifact versions. The change-impact domain traverses the graph, protects project/version boundaries, detects cycles, and propagates stale status. Phase 28 exposes graph/change-impact information to the workspace and release validation.

## Source versus derived

Canonical revisions are upstream sources. Drawings, diagrams, meshes, analysis outputs, quantities, costs, CAD/IFC exports and presentation boards are derived artifacts. A derived artifact must reference its source revision/hash and dependency lineage sufficiently to determine whether it is current.

## Staleness

When an upstream revision changes, affected descendants are marked stale. A stale artifact must not be presented as current or used as an authoritative downstream input without an explicit regeneration/revalidation path.

## Regeneration boundary

The current repository implements dependency invalidation/propagation, not the complete runtime:

```text
change
  -> dependency graph
  -> affected artifacts
  -> recomputation plan
  -> durable task queue
  -> worker
  -> validation
  -> new artifact version
  -> dependency rebinding
  -> current
```

Persisted tasks, leases, retries and idempotency already exist and are the intended infrastructure for this later runtime.

## Safety invariants

- Dependencies are version-scoped.
- Cross-project/version edges are rejected unless explicitly supported by a future contract.
- Cycles are rejected or safely detected before propagation.
- World Model hashes protect artifacts from silently binding to changed canonical inputs.
- Stale propagation is atomic with the change-impact transaction where required.
- Recomputed artifacts receive new versions; old artifacts remain available for history/audit.

## Planned extension

S3 will connect command commits to impact analysis and then to durable regeneration planning. It must reuse Phase 27 graph traversal and the existing task/lease/retry/idempotency infrastructure.

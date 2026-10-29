# Command Architecture

Canonical mutation is command-driven. The command system is the future convergence point for direct editing, AI proposals, undo/redo and dependency-aware regeneration.

## Command envelope

```text
command_id
 type
 schema_version
 actor
 project_id
 version_id
 base_revision_hash
 idempotency_key
 payload
 mode
 reason
```

## Mutation pipeline

```text
Command
  -> schema validation
  -> authorization
  -> semantic validation
  -> lock/concurrency validation
  -> draft application
  -> impact analysis
  -> preview
  -> user acceptance (when required)
  -> atomic commit
  -> new revision/hash
  -> audit event
  -> stale propagation
  -> regeneration planning
```

## Invariants

- A command is deterministic for the same canonical base revision, validated payload and deterministic engine version.
- Idempotency keys prevent duplicate commits.
- Base revision/hash protects against stale writes.
- Commands cannot bypass tenant/project/version authorization.
- AI proposals become commands only after schema and domain validation.
- Undo does not delete history; it creates a new revision representing the restored state.
- A failed validation leaves canonical state unchanged.

## Current repository state

The repository has versioning, idempotency, audit-oriented records and Phase 27 change-impact infrastructure, plus editing-related domain behavior. A single universal command bus has not yet replaced every mutation path. S3 is responsible for converging those paths without creating a second revision system.

The command registry is broader than the executable mutation adapters. In particular, `MoveBuilding` and `RotateBuilding` have payload contracts but no canonical World Model mutation adapter. The separate `ArchitecturalModel` domain has pure geometric transforms, but those transforms are not yet integrated with the World Model revision/command commit path. Do not expose either transform as executable until this authority boundary is resolved and end-to-end tests prove that canonical revisions, geometry, dependency invalidation, and regeneration remain consistent.

## Command examples planned

`SetSiteBoundary`, `MoveBuilding`, `RotateBuilding`, `ChangeSetback`, `AddLevel`, `ResizeSpace`, `MoveSpace`, `SetProgramArea`, `LockEntity`, followed by semantic building edits such as `MoveWall`, `ResizeWall`, `MoveDoor`, `MoveWindow`, `ChangeRoof`, `ChangeCore`, `ChangeFacade` and `ChangeGrid`.

## Proposal versus commit

A preview/proposal may be discarded. Only a successful command transaction may mutate canonical state. UI drag operations therefore represent an interaction stream; the committed geometry is produced by the command path.

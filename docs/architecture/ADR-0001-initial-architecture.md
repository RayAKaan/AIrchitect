# ADR-0001: Initial Architecture

**Status:** Accepted for MVP baseline; workflow runtime remains an explicit spike.

## Context
The product requires persistent canonical building state, deterministic engineering calculations, durable workflows, traceable artifacts, and an optional AI decision layer.

## Decision
- Modular monolith for domain/application/API code.
- Isolated workers for long-running and compute tasks.
- FastAPI + Pydantic backend; React + TypeScript + Vite frontend.
- PostgreSQL/PostGIS for canonical records and supported spatial operations.
- Object-storage abstraction for large artifacts; local filesystem adapter during early development.
- Deterministic local provider as the default decision provider.
- Domain-owned workflow/task contracts; evaluate Temporal in Phase 1 before committing to its runtime.
- Purpose-built Building World Model and trust/change lifecycle.

## Consequences
This minimizes early operational complexity while preserving boundaries for workers and external providers. The application must not expose workflow-engine-specific types through domain contracts. Local storage is development-only until access control, durability, and production object storage are validated.

# Frontend Architecture

## Purpose

AIrchitect's web client is a professional architectural workspace. The frontend is a projection and interaction layer over canonical backend revisions; it is not the source of truth for project, building, evidence, dependency, or artifact state.

## S0.4 boundary

The application entrypoint is intentionally small:

- `src/main.tsx` composes the router, providers, and application error boundary.
- `src/app/` owns application composition and cross-cutting lifecycle concerns.
- `src/state/` owns UI-only state such as selection, navigation, viewport, tools, and panels. Canonical domain state remains server-owned.
- `src/features/` owns user-facing capabilities. Existing feature folders remain in place and are migrated when touched rather than rewritten in one high-risk change.
- `src/adapters/` is the boundary for API, map, and renderer integrations as those integrations are migrated.
- `src/shared/` is reserved for reusable UI primitives, design tokens, hooks, units, and localization; feature-specific behavior must not move here.

The first migration moves the former monolithic `main.tsx` application into `app/App.tsx`, centralizes providers, adds an application error boundary, and introduces explicit workspace UI-state ownership with reducer coverage.

## Target workspace

```text
src/
  app/
    routing/
    providers/
    auth/
    shell/
    error-boundaries/
  shared/
    ui/
    tokens/
    hooks/
    units/
    i18n/
  state/
    selection/
    tool/
    viewport/
    panels/
    query-client/
  features/
    projects/
    site/
    brief/
    program/
    concepts/
    building/
    drawings/
    boards/
    review/
    history/
  adapters/
    api/
    map/
    renderer/
```

## State ownership

| State | Owner | Persistence |
|---|---|---|
| Authentication session | app/auth | session/browser storage until auth subsystem is migrated |
| Project list/query UI | app + state | UI only; reloads from API |
| Selected project/version/entity | state | UI only; canonical IDs come from API |
| Tool/viewport/panel state | state | UI only unless explicitly saved as a product artifact |
| Requirements, assumptions, World Model | backend canonical revisions | API/database |
| Evidence/provenance | backend | API/database |
| Dependency graph and stale state | backend Phase 27 infrastructure | API/database |
| Drawings/boards/analysis artifacts | backend artifact revisions | API/database/object storage as applicable |

## Interaction rule

Feature components may propose mutations through command/API adapters, but they must not invent or persist canonical domain state locally. Optimistic UI is allowed only when it can reconcile against the returned canonical revision and hash.

## Accessibility and professional-workspace direction

Future workspace components must support keyboard navigation, visible focus, semantic controls, ARIA where required, and WCAG 2.2 AA checks. The target shell is Top Toolbar + Left Rail + Canvas + Right Inspector + Bottom Status + Command Bar. Resizable panels, map/3D canvas adapters, and drawing/board workspaces will be introduced incrementally with the relevant product phases.

## Dependency policy

New frontend dependencies must be registered through the S0.3 compliance process before they become part of a release. The architecture prefers maintained, permissively licensed components and keeps map/rendering/provider-specific code behind adapters.

# Rendering Architecture

Rendering is a projection of canonical state. It is never the authority for geometry, measurements or compliance.

## Planned renderer contract

```text
Canonical / derived model
        |
        v
Renderer adapter
   +----+----+
   |         |
  2D        3D
```

The adapter owns scene conversion, loading, disposal, selection mapping and renderer-specific optimization. Domain code owns semantic meaning and geometry rules.

## Current frontend

The current web application is React/TypeScript/Vite with React Three Fiber/Three.js dependencies available in the project. `main.tsx` still contains substantial application shell and workspace state. The repository does not yet have the complete shared renderer adapter or unified 3D/Plan/Section/Elevation canvas described in the roadmap.

## Future benchmark gate

Before adopting a renderer architecture for production, benchmark representative models at approximately 10k, 100k and 1M geometry/entity scales. Measure load time, interaction FPS, memory, selection/edit latency and model switching. License and browser compatibility are release criteria, not afterthoughts.

## Selection identity

Rendered entities must map back to stable World Model/semantic IDs. Selection must therefore remain meaningful across views. A mesh UUID is not a canonical entity ID.

## Derived geometry

Meshes, fragments, GLB/glTF and renderer-specific buffers are disposable derived representations. They carry source revision/hash and generator/renderer version where persisted. They may be regenerated without changing canonical semantic state.

## Display versus calculation

Map display coordinates, camera transforms, GPU geometry and screen-space measurements are never authoritative calculation inputs. Calculation services consume explicit canonical geometry and declared CRS/units.

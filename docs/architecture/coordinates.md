# Coordinate Systems

AIrchitect uses explicit coordinate-system boundaries. No renderer/display coordinate system may become the authority for geometry calculations.

## Target canonical policy

| Context | CRS | Purpose | Authority |
|---|---|---|---|
| Geographic interchange | EPSG:4326 | GeoJSON and external geographic references | source/interchange |
| Site-local projected | provider/selected metric CRS | area, perimeter, setbacks, buffers, spatial analysis | geometry services |
| Building-local | local metric Cartesian coordinates | storeys, walls, openings, structural/architectural components | semantic building model |
| Web Mercator | EPSG:3857 | map display only | renderer |

## Rules

1. Every authoritative geometry record must declare its CRS.
2. Source CRS and transform identity must be retained when a geometry is transformed.
3. Area, perimeter, setback and spatial calculations must run in an appropriate projected metric CRS, never Web Mercator.
4. GeoJSON export/import uses EPSG:4326 unless a format/provider contract explicitly requires another CRS.
5. Building-local geometry is independent of geographic display coordinates; the mapping between them is explicit.
6. Precision/tolerance must be declared for authoritative geometry and comparison operations.
7. CRS mismatch is a validation error, not an implicit best-effort conversion.

## Current repository state

The existing geometry/CAD systems predate the complete Site World Model policy. They must be audited before the first Site implementation so existing geometry payloads can be mapped to this contract without silently changing units or coordinate meaning.

The current React application does not yet have a MapLibre-based authoritative site workspace. Web map coordinates will therefore remain a future adapter concern.

## Transformation record

Future site/building geometry transformations should retain:

- source CRS;
- target CRS;
- transformation/projection identifier;
- source geometry hash where practical;
- precision/tolerance;
- transformation runner/version;
- timestamp and actor/provider where applicable.

## Validation

Geometry services must reject invalid polygons, incompatible units and undeclared CRS. Repair operations must be deterministic and must produce a proposed corrected geometry rather than silently mutating canonical state.

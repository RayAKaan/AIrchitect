from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import Polygon, shape


@dataclass(frozen=True, slots=True)
class SiteBoundaryResult:
    geojson: dict[str, Any]
    area_m2: float
    perimeter_m: float
    calculation_crs: str
    warnings: tuple[str, ...]


def validate_boundary(boundary: dict[str, Any], *, min_area_m2: float = 1.0, max_area_m2: float = 10_000_000_000.0) -> SiteBoundaryResult:
    if boundary.get("type") != "Polygon":
        raise ValueError("SITE_BOUNDARY_MUST_BE_POLYGON")
    coordinates = boundary.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) != 1:
        raise ValueError("SITE_BOUNDARY_MUST_HAVE_ONE_EXTERIOR_RING")
    ring = coordinates[0]
    if not isinstance(ring, list) or len(ring) < 4:
        raise ValueError("SITE_BOUNDARY_RING_TOO_SHORT")
    if ring[0] != ring[-1]:
        raise ValueError("SITE_BOUNDARY_RING_MUST_BE_CLOSED")
    try:
        polygon = shape(boundary)
    except Exception as exc:
        raise ValueError("SITE_BOUNDARY_INVALID_GEOMETRY") from exc
    if not polygon.is_valid:
        raise ValueError(f"SITE_BOUNDARY_INVALID_GEOMETRY: {polygon.explain_validity() if hasattr(polygon, 'explain_validity') else 'self-intersection or invalid ring'}")
    if polygon.geom_type != "Polygon":
        raise ValueError("SITE_BOUNDARY_MUST_BE_POLYGON")
    if any(len(point) != 2 or not all(isfinite(float(value)) for value in point) for point in ring):
        raise ValueError("SITE_BOUNDARY_COORDINATES_INVALID")
    if any(not (-180 <= float(point[0]) <= 180 and -90 <= float(point[1]) <= 90) for point in ring):
        raise ValueError("SITE_BOUNDARY_COORDINATES_OUT_OF_RANGE")

    lon = sum(float(point[0]) for point in ring[:-1]) / (len(ring) - 1)
    lat = sum(float(point[1]) for point in ring[:-1]) / (len(ring) - 1)
    local_crs = CRS.from_proj4(f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs")
    transformer = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True)
    projected = Polygon([transformer.transform(float(x), float(y)) for x, y in ring])
    area_m2 = abs(projected.area)
    perimeter_m = projected.length
    if area_m2 < min_area_m2:
        raise ValueError("SITE_AREA_BELOW_MINIMUM")
    if area_m2 > max_area_m2:
        raise ValueError("SITE_AREA_ABOVE_MAXIMUM")

    normalized = dict(boundary)
    normalized["coordinates"] = [[list(point) for point in ring]]
    if Polygon([(float(x), float(y)) for x, y in ring]).exterior.is_ccw:
        normalized["coordinates"][0] = [list(point) for point in reversed(ring)]
        normalized["coordinates"][0] = [normalized["coordinates"][0][-1]] + normalized["coordinates"][0][:-1]
    return SiteBoundaryResult(normalized, area_m2, perimeter_m, local_crs.to_string(), ())

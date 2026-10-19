from __future__ import annotations

import hashlib
import json
from math import atan2, degrees, pi
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import shape
from shapely.ops import transform as transform_geometry

from app.db.site_models import SiteRevision, SiteLayerSnapshot

RUNNER_VERSION = "site-analysis-1.2.0"
CONTEXT_RADIUS_M = 250.0


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _projected_geometry(geometry: Any, revision: SiteRevision):
    source = CRS.from_epsg(4326)
    target = CRS.from_user_input(revision.calculation_crs)
    transformer = Transformer.from_crs(source, target, always_xy=True)
    return transform_geometry(transformer.transform, geometry)


def _category(properties: dict[str, Any]) -> str:
    for key in ("layer", "category", "class", "type", "land_use"):
        value = properties.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower().replace("_", " ")
    return "unknown"


def _is(category: str, *terms: str) -> bool:
    return any(term in category for term in terms)


def _road_hierarchy(properties: dict[str, Any], category: str) -> str:
    for key in ("highway", "road_class", "road_hierarchy", "hierarchy"):
        value = properties.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower().replace("_", " ")
    return "unknown"


def _solar_orientation(revision: SiteRevision) -> dict[str, Any]:
    ring = revision.boundary_geojson["coordinates"][0]
    sectors = {"north": 0, "east": 0, "south": 0, "west": 0}
    bearings: list[float] = []
    for first, second in zip(ring, ring[1:]):
        dx = float(second[0]) - float(first[0]); dy = float(second[1]) - float(first[1])
        if dx == 0 and dy == 0: continue
        bearing = (degrees(atan2(dx, dy)) + 360.0) % 360.0
        bearings.append(round(bearing, 3))
        if bearing >= 315 or bearing < 45: sectors["north"] += 1
        elif bearing < 135: sectors["east"] += 1
        elif bearing < 225: sectors["south"] += 1
        else: sectors["west"] += 1
    return {"edge_bearings_deg": bearings, "edge_orientation_counts": sectors, "method": "boundary_edge_orientation_only"}


def analyze_site(revision: SiteRevision, snapshots: list[SiteLayerSnapshot]) -> dict[str, Any]:
    ordered = sorted(snapshots, key=lambda item: item.id)
    source_hash = _hash([{"id": item.id, "provider": item.provider, "dataset_version": item.dataset_version, "payload": item.payload_json} for item in ordered])
    site_polygon = _projected_geometry(shape(revision.boundary_geojson), revision)
    context_zone = site_polygon.buffer(CONTEXT_RADIUS_M)
    buildings_area = green_area = water_area = road_length = 0.0
    building_count = road_count = green_count = water_count = 0
    context_feature_count = transit_feature_count = 0
    context_intersection_area_m2 = 0.0
    land_use_counts: dict[str, int] = {}
    road_hierarchy_counts: dict[str, int] = {}
    road_frontage_m = 0.0

    for snapshot in ordered:
        payload = snapshot.payload_json
        if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection": continue
        for feature in payload.get("features", []):
            if not isinstance(feature, dict) or not isinstance(feature.get("geometry"), dict): continue
            try:
                geometry = _projected_geometry(shape(feature["geometry"]), revision)
                clipped = geometry.intersection(site_polygon)
                context_clipped = geometry.intersection(context_zone)
            except Exception:
                continue
            if not context_clipped.is_empty:
                context_feature_count += 1
                context_intersection_area_m2 += float(context_clipped.area) if hasattr(context_clipped, "area") else 0.0
            category = _category(feature.get("properties") or {})
            properties = feature.get("properties") or {}
            if _is(category, "transit", "station", "bus", "rail", "metro", "tram"):
                transit_feature_count += 1
            if clipped.is_empty: continue
            land_use = str(properties.get("land_use", "")).strip().lower()
            if land_use: land_use_counts[land_use] = land_use_counts.get(land_use, 0) + 1
            if _is(category, "building", "structure"):
                building_count += 1; buildings_area += float(clipped.area)
            if _is(category, "road", "street", "highway"):
                road_count += 1; road_length += float(clipped.length)
                road_frontage_m += float(clipped.intersection(site_polygon.boundary).length)
                hierarchy = _road_hierarchy(properties, category)
                road_hierarchy_counts[hierarchy] = road_hierarchy_counts.get(hierarchy, 0) + 1
            if _is(category, "green", "park", "vegetation"):
                green_count += 1; green_area += float(clipped.area)
            if _is(category, "water", "river", "lake"):
                water_count += 1; water_area += float(clipped.area)

    compactness = (4 * pi * revision.area_m2 / (revision.perimeter_m ** 2)) if revision.perimeter_m else 0.0
    warnings: list[str] = []
    if not ordered: warnings.append("NO_CONTEXT_SNAPSHOTS")
    if building_count == 0: warnings.append("NO_BUILDING_CONTEXT")
    if road_count == 0: warnings.append("NO_ROAD_CONTEXT")
    if not land_use_counts: warnings.append("NO_LAND_USE_CONTEXT")
    return {
        "runner_version": RUNNER_VERSION, "site_revision_id": revision.id, "site_revision_hash": revision.content_hash,
        "source_context_hash": source_hash,
        "metrics": {
            "site_area_m2": revision.area_m2, "site_perimeter_m": revision.perimeter_m,
            "site_compactness_ratio": round(compactness, 6), "built_area_m2": round(buildings_area, 3),
            "building_coverage_ratio": round(buildings_area / revision.area_m2, 6) if revision.area_m2 else 0.0,
            "building_feature_count": building_count, "road_feature_count": road_count,
            "road_length_m": round(road_length, 3), "road_density_m_per_ha": round(road_length / (revision.area_m2 / 10000), 3) if revision.area_m2 else 0.0,
            "road_frontage_m": round(road_frontage_m, 3), "green_area_m2": round(green_area, 3),
            "green_feature_count": green_count, "green_ratio": round(green_area / revision.area_m2, 6) if revision.area_m2 else 0.0,
            "water_area_m2": round(water_area, 3), "water_feature_count": water_count,
            "water_ratio": round(water_area / revision.area_m2, 6) if revision.area_m2 else 0.0,
            "context_radius_m": CONTEXT_RADIUS_M, "context_feature_count": context_feature_count,
            "context_intersection_area_m2": round(context_intersection_area_m2, 3),
            "road_hierarchy_counts": dict(sorted(road_hierarchy_counts.items())),
            "transit_feature_count": transit_feature_count,
            "land_use_counts": dict(sorted(land_use_counts.items())),
        },
        "solar": _solar_orientation(revision),
        "environmental": {"climate": {"status": "UNKNOWN", "reason": "No climate provider is bound to this analysis."}, "terrain": {"status": "UNKNOWN", "reason": "No DEM/terrain provider is bound to this analysis."}},
        "warnings": warnings,
        "status": "SUPPORTED" if ordered else "UNKNOWN",
        "evidence_policy": "Derived metrics inherit the status of the persisted context snapshots; no regulatory, climate or terrain claim is inferred.",
    }

from __future__ import annotations

import hashlib
import json
from math import atan2, degrees
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import shape
from shapely.ops import transform as transform_geometry

from app.db.site_models import SiteRevision, SiteLayerSnapshot

RUNNER_VERSION = "site-analysis-1.0.0"


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


def _solar_orientation(revision: SiteRevision) -> dict[str, Any]:
    ring = revision.boundary_geojson["coordinates"][0]
    sectors = {"north": 0, "east": 0, "south": 0, "west": 0}
    bearings: list[float] = []
    for first, second in zip(ring, ring[1:]):
        dx = float(second[0]) - float(first[0])
        dy = float(second[1]) - float(first[1])
        if dx == 0 and dy == 0:
            continue
        bearing = (degrees(atan2(dx, dy)) + 360.0) % 360.0
        bearings.append(round(bearing, 3))
        if bearing >= 315 or bearing < 45: sectors["north"] += 1
        elif bearing < 135: sectors["east"] += 1
        elif bearing < 225: sectors["south"] += 1
        else: sectors["west"] += 1
    return {"edge_bearings_deg": bearings, "edge_orientation_counts": sectors, "method": "boundary_edge_orientation_only"}


def analyze_site(revision: SiteRevision, snapshots: list[SiteLayerSnapshot]) -> dict[str, Any]:
    ordered = sorted(snapshots, key=lambda item: item.id)
    source_hash = _hash([{ "id": item.id, "provider": item.provider, "dataset_version": item.dataset_version, "payload": item.payload_json } for item in ordered])
    site_polygon = _projected_geometry(shape(revision.boundary_geojson), revision)
    buildings_area = 0.0
    green_area = 0.0
    water_area = 0.0
    road_length = 0.0
    building_count = 0
    road_count = 0
    green_count = 0
    water_count = 0
    land_use_counts: dict[str, int] = {}

    for snapshot in ordered:
        payload = snapshot.payload_json
        if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
            continue
        for feature in payload.get("features", []):
            if not isinstance(feature, dict) or not isinstance(feature.get("geometry"), dict):
                continue
            try:
                geometry = _projected_geometry(shape(feature["geometry"]), revision)
                clipped = geometry.intersection(site_polygon)
            except Exception:
                continue
            if clipped.is_empty:
                continue
            category = _category(feature.get("properties") or {})
            land_use = str((feature.get("properties") or {}).get("land_use", "")).strip().lower()
            if land_use:
                land_use_counts[land_use] = land_use_counts.get(land_use, 0) + 1
            if _is(category, "building", "structure"):
                building_count += 1; buildings_area += float(clipped.area)
            if _is(category, "road", "street", "highway"):
                road_count += 1; road_length += float(clipped.length)
            if _is(category, "green", "park", "vegetation"):
                green_count += 1; green_area += float(clipped.area)
            if _is(category, "water", "river", "lake"):
                water_count += 1; water_area += float(clipped.area)

    warnings: list[str] = []
    if not ordered: warnings.append("NO_CONTEXT_SNAPSHOTS")
    if building_count == 0: warnings.append("NO_BUILDING_CONTEXT")
    if road_count == 0: warnings.append("NO_ROAD_CONTEXT")
    if not land_use_counts: warnings.append("NO_LAND_USE_CONTEXT")
    return {
        "runner_version": RUNNER_VERSION,
        "site_revision_id": revision.id,
        "site_revision_hash": revision.content_hash,
        "source_context_hash": source_hash,
        "metrics": {
            "site_area_m2": revision.area_m2,
            "site_perimeter_m": revision.perimeter_m,
            "built_area_m2": round(buildings_area, 3),
            "building_coverage_ratio": round(buildings_area / revision.area_m2, 6) if revision.area_m2 else 0.0,
            "building_feature_count": building_count,
            "road_feature_count": road_count,
            "road_length_m": round(road_length, 3),
            "green_area_m2": round(green_area, 3),
            "green_feature_count": green_count,
            "water_area_m2": round(water_area, 3),
            "water_feature_count": water_count,
            "land_use_counts": dict(sorted(land_use_counts.items())),
        },
        "solar": _solar_orientation(revision),
        "warnings": warnings,
        "status": "SUPPORTED" if ordered else "UNKNOWN",
        "evidence_policy": "Derived metrics inherit the status of the persisted context snapshots; no regulatory or climate claim is inferred.",
    }

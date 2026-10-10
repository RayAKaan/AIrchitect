from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

SEMANTIC_SCHEMA_VERSION = "1.0.0"
GEOMETRY_MAPPING_VERSION = "1.0.0"

# Mappings are descriptive contracts for the CAD/BIM adapter. They do not claim
# that an element has valid solid geometry unless all required dimensions exist.
CAD_MAPPINGS: dict[str, dict[str, Any]] = {
    "Site": {"ifc_class": "IfcSite", "cad_feature": "site_reference", "required": []},
    "Building": {"ifc_class": "IfcBuilding", "cad_feature": "building_container", "required": []},
    "Storey": {"ifc_class": "IfcBuildingStorey", "cad_feature": "storey_reference", "required": []},
    "Space": {"ifc_class": "IfcSpace", "cad_feature": "space_reference", "required": ["area_m2"]},
    "ParkingFacility": {"ifc_class": "IfcSpace", "cad_feature": "parking_program", "required": ["spaces"]},
    "Wall": {"ifc_class": "IfcWall", "cad_feature": "wall_extrusion", "required": ["length_m", "height_m", "thickness_m"]},
    "Slab": {"ifc_class": "IfcSlab", "cad_feature": "slab_extrusion", "required": ["width_m", "depth_m", "thickness_m"]},
    "Roof": {"ifc_class": "IfcRoof", "cad_feature": "roof_profile", "required": ["footprint_width_m", "footprint_depth_m"]},
    "Door": {"ifc_class": "IfcDoor", "cad_feature": "door_opening", "required": ["width_m", "height_m"]},
    "Window": {"ifc_class": "IfcWindow", "cad_feature": "window_opening", "required": ["width_m", "height_m"]},
}


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stable_id(project_id: str, element_type: str, key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"airchitect:{project_id}:{element_type}:{key}"))


def _quantity(value: Any, unit: str | None = None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict) and "value" in value:
        return {"value": value["value"], "unit": value.get("unit", unit)}
    if isinstance(value, (str, int, float, bool)):
        return {"value": value, "unit": unit}
    return None


def _property(value: Any, unit: str | None = None, data_type: str | None = None) -> dict[str, Any] | None:
    quantity = _quantity(value, unit)
    if quantity is None:
        return None
    raw = quantity["value"]
    inferred = data_type or ("boolean" if isinstance(raw, bool) else "integer" if isinstance(raw, int)
                             else "number" if isinstance(raw, float) else "string")
    return {"value": raw, "unit": quantity.get("unit"), "data_type": inferred}


def compile_semantic_model(world_model: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic semantic graph from the verified canonical model.

    IDs are project-scoped and independent of mutable values, so changing a floor
    height does not silently replace the identity of the building or storey.
    Missing architectural components remain absent and are listed as unknowns;
    this compiler never invents walls, doors, windows, or dimensions.
    """
    project_id = str(world_model.get("project_id") or "")
    version_id = str(world_model.get("project_version_id") or "")
    if not project_id or not version_id:
        raise ValueError("canonical World Model must include project_id and project_version_id")

    source = {key: value for key, value in world_model.items() if key != "semantic_model"}
    source_hash = canonical_hash(source)
    site = world_model.get("site") or {}
    building = world_model.get("building") or {}
    levels = world_model.get("levels") or []
    spaces = world_model.get("spaces") or []
    parking = world_model.get("parking") or {}
    provenance = world_model.get("provenance") or {}
    elements: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []

    def add_element(element_type: str, key: str, name: str, properties: dict[str, Any],
                    provenance_keys: list[str] | None = None) -> str:
        element_id = _stable_id(project_id, element_type, key)
        mapping = CAD_MAPPINGS[element_type]
        elements.append({
            "id": element_id,
            "element_type": element_type,
            "name": name,
            "properties": {k: v for k, v in properties.items() if v is not None},
            "provenance": {
                parameter: provenance[parameter]
                for parameter in (provenance_keys or [])
                if parameter in provenance
            },
            "cad_mapping": {
                "ifc_class": mapping["ifc_class"],
                "cad_feature": mapping["cad_feature"],
                "required_parameters": mapping["required"],
            },
            "identity_key": key,
        })
        return element_id

    def add_relationship(source_id: str, relationship_type: str, target_id: str) -> None:
        rel_id = str(uuid5(NAMESPACE_URL, f"airchitect:{project_id}:relationship:{source_id}:{relationship_type}:{target_id}"))
        relationships.append({"id": rel_id, "source_id": source_id, "relationship_type": relationship_type,
                              "target_id": target_id})

    site_id = add_element("Site", "site", "Site", {
        "area_m2": _property(site.get("area"), "m2"),
        "city": _property((site.get("location") or {}).get("city"), data_type="string"),
        "country": _property((site.get("location") or {}).get("country"), data_type="string"),
    }, ["site_area", "city"])
    building_id = add_element("Building", "building", "Building", {
        "use": _property(building.get("use"), data_type="string"),
        "floor_count": _property(building.get("floor_count"), "count"),
        "height_m": _property(building.get("height"), "m"),
        "floor_to_floor_height_m": _property(building.get("floor_to_floor_height"), "m"),
        "target_gfa_m2": _property(building.get("target_gfa"), "m2"),
    }, ["building_use", "floor_count", "building_height", "floor_to_floor_height", "target_gfa"])
    add_relationship(building_id, "located_on", site_id)

    level_ids: dict[int, str] = {}
    for level in levels:
        number = int(level["level_number"])
        level_id = add_element("Storey", f"level:{number}", str(level.get("name") or f"Level {number}"), {
            "level_number": _property(number, "count"),
            "elevation_m": _property(level.get("elevation"), "m"),
            "floor_to_floor_height_m": _property(level.get("floor_to_floor_height"), "m"),
            "area_m2": _property(level.get("area"), "m2"),
        }, ["floor_count", "floor_to_floor_height", "target_gfa"])
        level_ids[number] = level_id
        add_relationship(building_id, "has_storey", level_id)

    for space in spaces:
        key = str(space.get("id") or space.get("name") or len(elements))
        space_id = add_element("Space", key, str(space.get("name") or "Unspecified space"), {
            "use": _property(space.get("use"), data_type="string"),
            "area_m2": _property(space.get("area"), "m2"),
        })
        number = space.get("level_number")
        if number is not None and int(number) in level_ids:
            add_relationship(level_ids[int(number)], "contains_space", space_id)

    if parking.get("arrangement") is not None or parking.get("spaces") is not None:
        parking_id = add_element("ParkingFacility", "parking", "Parking", {
            "arrangement": _property(parking.get("arrangement"), data_type="string"),
            "spaces": _property(parking.get("spaces"), "count"),
        }, ["parking_arrangement", "parking_spaces"])
        add_relationship(building_id, "includes_facility", parking_id)

    element_types_present = sorted({element["element_type"] for element in elements})
    architectural_types_not_modelled = ["Wall", "Slab", "Roof", "Door", "Window"]
    unknowns = sorted(set(world_model.get("unknowns") or []))
    unknowns.extend(f"semantic_element:{kind}" for kind in architectural_types_not_modelled)
    return {
        "schema_version": SEMANTIC_SCHEMA_VERSION,
        "project_id": project_id,
        "project_version_id": version_id,
        "source_world_model_hash": source_hash,
        "elements": elements,
        "relationships": sorted(relationships, key=lambda row: (row["source_id"], row["relationship_type"], row["target_id"])),
        "element_types_present": element_types_present,
        "element_types_not_modelled": architectural_types_not_modelled,
        "unknowns": sorted(set(unknowns)),
    }


def compile_parametric_geometry(world_model: dict[str, Any], semantic_model: dict[str, Any]) -> dict[str, Any]:
    """Compile semantic entities into explicit CAD/BIM feature intents, not fake solids."""
    building = world_model.get("building") or {}
    properties = world_model.get("properties") or {}
    width = building.get("footprint_width_m", properties.get("footprint_width_m"))
    depth = building.get("footprint_depth_m", properties.get("footprint_depth_m"))
    floor_count = building.get("floor_count")
    floor_height = building.get("floor_to_floor_height")
    if isinstance(floor_height, dict):
        floor_height = floor_height.get("value")

    intents: list[dict[str, Any]] = []
    for element in semantic_model.get("elements", []):
        element_type = element["element_type"]
        mapping = CAD_MAPPINGS[element_type]
        params: dict[str, Any] = {}
        missing: list[str] = []
        if element_type == "Building":
            if width is None or float(width) <= 0:
                missing.append("footprint_width_m")
            else:
                params["footprint_width_m"] = float(width)
            if depth is None or float(depth) <= 0:
                missing.append("footprint_depth_m")
            else:
                params["footprint_depth_m"] = float(depth)
            if floor_count is None or int(floor_count) < 1:
                missing.append("floor_count")
            else:
                params["floor_count"] = int(floor_count)
            if floor_height is None or float(floor_height) <= 0:
                missing.append("floor_to_floor_height_m")
            else:
                params["floor_to_floor_height_m"] = float(floor_height)
            feature = "stacked_floor_plate_mass"
        elif element_type == "Storey":
            if width is None or float(width) <= 0 or depth is None or float(depth) <= 0:
                missing.append("footprint_width_m_and_footprint_depth_m")
            else:
                params["footprint_width_m"] = float(width)
                params["footprint_depth_m"] = float(depth)
            if floor_height is None or float(floor_height) <= 0:
                missing.append("floor_to_floor_height_m")
            else:
                params["floor_to_floor_height_m"] = float(floor_height)
            feature = "storey_slab"
        else:
            element_properties = element.get("properties") or {}
            for required in mapping["required"]:
                item = element_properties.get(required)
                if not isinstance(item, dict) or item.get("value") is None:
                    missing.append(required)
                else:
                    params[required] = item["value"]
            feature = mapping["cad_feature"]

        status = "READY_FOR_CAD_ADAPTER" if not missing else "UNDERCONSTRAINED"
        intents.append({
            "element_id": element["id"],
            "element_type": element_type,
            "feature": feature,
            "mapping_version": GEOMETRY_MAPPING_VERSION,
            "ifc_class": mapping["ifc_class"],
            "parameters": params,
            "missing_parameters": sorted(set(missing)),
            "status": status,
        })

    ready = all(intent["status"] == "READY_FOR_CAD_ADAPTER" for intent in intents) and bool(intents)
    payload = {
        "schema_version": GEOMETRY_MAPPING_VERSION,
        "project_id": semantic_model["project_id"],
        "project_version_id": semantic_model["project_version_id"],
        "source_world_model_hash": semantic_model["source_world_model_hash"],
        "semantic_model_hash": canonical_hash(semantic_model),
        "status": "READY_FOR_CAD_ADAPTER" if ready else "UNDERCONSTRAINED",
        "intents": intents,
        "limitations": [
            "This is a deterministic parametric feature specification, not a generated B-rep or IFC file.",
            "No wall, slab, roof, door, or window geometry is inferred without explicit dimensions and relationships.",
            "Native CAD/BIM generation and geometry validation remain the responsibility of the isolated CAD worker.",
        ],
    }
    payload["specification_hash"] = canonical_hash(payload)
    return payload

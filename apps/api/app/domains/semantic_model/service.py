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
        "width_m": _property(site.get("width"), "m"),
        "depth_m": _property(site.get("depth"), "m"),
        "orientation_deg": _property(site.get("orientation"), "degree"),
        "city": _property((site.get("location") or {}).get("city"), data_type="string"),
        "country": _property((site.get("location") or {}).get("country"), data_type="string"),
    }, ["site_area", "city"])
    building_id = add_element("Building", "building", "Building", {
        "use": _property(building.get("use"), data_type="string"),
        "floor_count": _property(building.get("floor_count"), "count"),
        "height_m": _property(building.get("height"), "m"),
        "floor_to_floor_height_m": _property(building.get("floor_to_floor_height"), "m"),
        "target_gfa_m2": _property(building.get("target_gfa"), "m2"),
        "coverage_ratio": _property(building.get("coverage"), data_type="number"),
        "footprint_width_m": _property((world_model.get("properties") or {}).get("footprint_width_m"), "m"),
        "footprint_depth_m": _property((world_model.get("properties") or {}).get("footprint_depth_m"), "m"),
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

    # Designer-authored components are explicit user-authored facts. They are
    # never inferred from a brief and retain their stable IDs across revisions.
    existing_ids = {element["id"] for element in elements}
    for authored in world_model.get("designer_elements") or []:
        element_type = authored.get("element_type")
        if element_type not in CAD_MAPPINGS:
            continue
        element_id = str(authored.get("id") or "")
        if not element_id or element_id in existing_ids:
            continue
        mapping = CAD_MAPPINGS[element_type]
        properties = authored.get("properties") or {}
        elements.append({
            "id": element_id,
            "element_type": element_type,
            "name": str(authored.get("name") or element_type),
            "properties": properties,
            "provenance": authored.get("provenance") or {},
            "cad_mapping": {
                "ifc_class": mapping["ifc_class"],
                "cad_feature": mapping["cad_feature"],
                "required_parameters": mapping["required"],
            },
            "identity_key": str(authored.get("identity_key") or element_id),
            "designer_authored": True,
        })
        existing_ids.add(element_id)

    allowed_relationships = {"located_on", "has_storey", "contains_space", "includes_facility",
                             "contains_element", "hosts_element", "hosts_opening"}
    for relationship in world_model.get("designer_relationships") or []:
        source_id, target_id = relationship.get("source_id"), relationship.get("target_id")
        if source_id not in existing_ids or target_id not in existing_ids:
            raise ValueError("designer relationship references a missing semantic element")
        relationship_type = str(relationship.get("relationship_type") or "")
        if relationship_type not in allowed_relationships:
            raise ValueError(f"unsupported designer relationship type: {relationship_type}")
        add_relationship(str(source_id), relationship_type, str(target_id))

    element_types_present = sorted({element["element_type"] for element in elements})
    architectural_types_not_modelled = [kind for kind in ["Wall", "Slab", "Roof", "Door", "Window"]
                                        if kind not in element_types_present]
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


def compile_parametric_geometry(world_model: dict[str, Any], semantic_model: dict[str, Any],
                                 element_ids: set[str] | None = None) -> dict[str, Any]:
    """Compile all or selected semantic entities into CAD/BIM feature intents, not fake solids."""
    building = world_model.get("building") or {}
    properties = world_model.get("properties") or {}
    width = building.get("footprint_width_m", properties.get("footprint_width_m"))
    depth = building.get("footprint_depth_m", properties.get("footprint_depth_m"))
    floor_count = building.get("floor_count")
    floor_height = building.get("floor_to_floor_height")
    if isinstance(floor_height, dict):
        floor_height = floor_height.get("value")

    intents: list[dict[str, Any]] = []
    storey_area_issue = next((issue for issue in world_model.get("consistency_issues", [])
                              if issue.get("code") == "STOREY_AREA_GFA_INCONSISTENCY"), None)
    selected_elements = semantic_model.get("elements", [])
    if element_ids is not None:
        selected_elements = [element for element in selected_elements if element.get("id") in element_ids]
    for element in selected_elements:
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
            element_properties = element.get("properties") or {}
            if width is None or float(width) <= 0 or depth is None or float(depth) <= 0:
                missing.append("footprint_width_m_and_footprint_depth_m")
            else:
                params["footprint_width_m"] = float(width)
                params["footprint_depth_m"] = float(depth)
            storey_height = element_properties.get("floor_to_floor_height_m")
            storey_height = storey_height.get("value") if isinstance(storey_height, dict) else floor_height
            if storey_height is None or float(storey_height) <= 0:
                missing.append("floor_to_floor_height_m")
            else:
                params["floor_to_floor_height_m"] = float(storey_height)
            storey_elevation = element_properties.get("elevation_m")
            if isinstance(storey_elevation, dict) and storey_elevation.get("value") is not None:
                params["elevation_m"] = float(storey_elevation["value"])
            storey_area = element_properties.get("area_m2")
            if isinstance(storey_area, dict) and storey_area.get("value") is not None:
                params["target_area_m2"] = float(storey_area["value"])
                footprint_area = params.get("footprint_width_m", 0) * params.get("footprint_depth_m", 0)
                if footprint_area > 0 and float(storey_area["value"]) > footprint_area + max(1.0, footprint_area * 0.01):
                    missing.append("area_dimension_review")
            feature = "storey_slab"
        else:
            element_properties = element.get("properties") or {}
            for required in mapping["required"]:
                item = element_properties.get(required)
                if not isinstance(item, dict) or item.get("value") is None:
                    missing.append(required)
                else:
                    params[required] = item["value"]
            if element_type in {"Door", "Window"}:
                host_ids = {relationship.get("source_id") for relationship in semantic_model.get("relationships", [])
                            if relationship.get("target_id") == element["id"]
                            and relationship.get("relationship_type") == "hosts_opening"}
                wall_ids = {item["id"] for item in semantic_model.get("elements", []) if item.get("element_type") == "Wall"}
                if not host_ids.intersection(wall_ids):
                    missing.append("host_wall_id")
            feature = mapping["cad_feature"]

        placement: dict[str, Any] | None = None
        relationships = semantic_model.get("relationships", [])
        elements_by_id = {candidate["id"]: candidate for candidate in semantic_model.get("elements", [])}
        placement_source_id = element["id"] if element_type == "Storey" else next((relationship["source_id"] for relationship in relationships
            if relationship.get("target_id") == element["id"]
            and relationship.get("relationship_type") in {"hosts_element", "contains_space", "contains_element"}
            and elements_by_id.get(relationship.get("source_id"), {}).get("element_type") == "Storey"), None)
        if element_type in {"Door", "Window"}:
            host_id = next((relationship.get("source_id") for relationship in relationships
                if relationship.get("target_id") == element["id"]
                and relationship.get("relationship_type") == "hosts_opening"), None)
            if host_id is not None:
                placement_source_id = next((relationship["source_id"] for relationship in relationships
                    if relationship.get("target_id") == host_id
                    and relationship.get("relationship_type") in {"hosts_element", "contains_element"}
                    and elements_by_id.get(relationship.get("source_id"), {}).get("element_type") == "Storey"), None)
        storey = elements_by_id.get(placement_source_id)
        if storey is not None:
            storey_properties = storey.get("properties") or {}
            level_number = storey_properties.get("level_number")
            elevation = storey_properties.get("elevation_m")
            placement = {
                "storey_id": storey["id"],
                "level_number": level_number.get("value") if isinstance(level_number, dict) else None,
                "elevation_m": elevation.get("value") if isinstance(elevation, dict) else None,
            }
        elif element_type in {"Space", "Wall", "Slab", "Roof", "Door", "Window"}:
            missing.append("storey_placement")
        warnings = []
        if storey_area_issue and element_type in {"Building", "Storey"}:
            warnings.append(storey_area_issue.get("message") or "Storey areas do not reconcile with target GFA; review before native CAD generation.")
        if "area_dimension_review" in missing:
            warnings.append("Explicit storey area conflicts with the footprint dimensions; resolve the dimensions before native CAD generation.")
            missing.remove("area_dimension_review")
        status = ("REVIEW_REQUIRED" if warnings else
                  "READY_FOR_CAD_ADAPTER" if not missing else "UNDERCONSTRAINED")
        intents.append({
            "element_id": element["id"],
            "element_type": element_type,
            "feature": feature,
            "mapping_version": GEOMETRY_MAPPING_VERSION,
            "ifc_class": mapping["ifc_class"],
            "parameters": params,
            "placement": placement,
            "missing_parameters": sorted(set(missing)),
            "warnings": warnings,
            "status": status,
        })

    ready = all(intent["status"] == "READY_FOR_CAD_ADAPTER" for intent in intents) and bool(intents)
    review_required = any(intent["status"] == "REVIEW_REQUIRED" for intent in intents)
    payload = {
        "schema_version": GEOMETRY_MAPPING_VERSION,
        "project_id": semantic_model["project_id"],
        "project_version_id": semantic_model["project_version_id"],
        "source_world_model_hash": semantic_model["source_world_model_hash"],
        "semantic_model_hash": canonical_hash(semantic_model),
        "status": "REVIEW_REQUIRED" if review_required else "READY_FOR_CAD_ADAPTER" if ready else "UNDERCONSTRAINED",
        "intents": intents,
        "limitations": [
            "This is a deterministic parametric feature specification, not a generated B-rep or IFC file.",
            "No wall, slab, roof, door, or window geometry is inferred without explicit dimensions and relationships.",
            "Native CAD/BIM generation and geometry validation remain the responsibility of the isolated CAD worker.",
        ],
    }
    payload["specification_hash"] = canonical_hash(payload)
    return payload

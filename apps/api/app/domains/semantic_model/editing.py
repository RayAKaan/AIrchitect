from __future__ import annotations

import copy
import math
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, ProjectVersion, User, WorldModelRevision
from app.domains.lifecycle.service import canonical_hash
from app.domains.semantic_model.service import CAD_MAPPINGS, compile_semantic_model
from app.domains.foundation.service import audit, error, resolve_project_version, resolve_world_model

# Only these semantic properties can be changed through the designer API. The
# unit and value type are server-owned; clients cannot relabel a number as a unit.
PROPERTY_SPECS: dict[str, dict[str, dict[str, Any]]] = {
    "Site": {
        "area_m2": {"kind": "number", "unit": "m2", "minimum": 0.01, "maximum": 1_000_000_000},
        "width_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 100_000},
        "depth_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 100_000},
        "orientation_deg": {"kind": "number", "unit": "degree", "minimum": 0, "maximum": 360},
        "city": {"kind": "string", "unit": None},
    },
    "Building": {
        "use": {"kind": "string", "unit": None},
        "floor_count": {"kind": "integer", "unit": "count", "minimum": 1, "maximum": 100},
        "floor_to_floor_height_m": {"kind": "number", "unit": "m", "minimum": 0.1, "maximum": 20},
        "height_m": {"kind": "number", "unit": "m", "minimum": 0.1, "maximum": 1000},
        "target_gfa_m2": {"kind": "number", "unit": "m2", "minimum": 0.01, "maximum": 1_000_000_000},
        "coverage_ratio": {"kind": "number", "unit": None, "minimum": 0, "maximum": 1},
        "footprint_width_m": {"kind": "number", "unit": "m", "minimum": 0.1, "maximum": 100_000},
        "footprint_depth_m": {"kind": "number", "unit": "m", "minimum": 0.1, "maximum": 100_000},
    },
    "Storey": {
        "elevation_m": {"kind": "number", "unit": "m", "minimum": -1_000, "maximum": 10_000},
        "floor_to_floor_height_m": {"kind": "number", "unit": "m", "minimum": 0.1, "maximum": 20},
        "area_m2": {"kind": "number", "unit": "m2", "minimum": 0.01, "maximum": 1_000_000_000},
    },
    "Space": {
        "use": {"kind": "string", "unit": None},
        "area_m2": {"kind": "number", "unit": "m2", "minimum": 0.01},
        "level_number": {"kind": "integer", "unit": "count", "minimum": 1, "maximum": 100},
    },
    "ParkingFacility": {
        "arrangement": {"kind": "string", "unit": None},
        "spaces": {"kind": "integer", "unit": "count", "minimum": 0, "maximum": 1_000_000},
    },
    "Wall": {
        "level_number": {"kind": "integer", "unit": "count", "minimum": 1, "maximum": 300},
        "length_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 100_000},
        "height_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 1_000},
        "thickness_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 10},
    },
    "Slab": {
        "level_number": {"kind": "integer", "unit": "count", "minimum": 1, "maximum": 300},
        "width_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 100_000},
        "depth_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 100_000},
        "thickness_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 10},
    },
    "Roof": {
        "level_number": {"kind": "integer", "unit": "count", "minimum": 1, "maximum": 300},
        "footprint_width_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 100_000},
        "footprint_depth_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 100_000},
    },
    "Door": {
        "width_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 100},
        "height_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 100},
    },
    "Window": {
        "width_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 100},
        "height_m": {"kind": "number", "unit": "m", "minimum": 0.01, "maximum": 100},
    },
}

CREATABLE_TYPES = {"Space", "Wall", "Slab", "Roof", "Door", "Window"}
GEOMETRY_PROPERTIES = {
    "area_m2", "width_m", "depth_m", "orientation_deg", "floor_count",
    "floor_to_floor_height_m", "height_m", "target_gfa_m2", "coverage_ratio",
    "footprint_width_m", "footprint_depth_m", "elevation_m", "level_number",
    "length_m", "thickness_m", "spaces",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def initial_designer_state() -> dict[str, Any]:
    return {"schema_version": "1.0.0", "locks": {}, "overrides": {}, "history": [],
            "undo_stack": [], "redo_stack": []}


def state_for(model: dict[str, Any]) -> dict[str, Any]:
    state = copy.deepcopy(model.get("designer_state") or initial_designer_state())
    state.setdefault("schema_version", "1.0.0")
    state.setdefault("locks", {})
    state.setdefault("overrides", {})
    state.setdefault("history", [])
    state.setdefault("undo_stack", [])
    state.setdefault("redo_stack", [])
    return state


def _element(model: dict[str, Any], element_id: str) -> dict[str, Any]:
    semantic = model.get("semantic_model")
    if not isinstance(semantic, dict) or not semantic.get("elements"):
        semantic = compile_semantic_model(model)
    found = next((item for item in semantic["elements"] if item.get("id") == element_id), None)
    if found is None:
        raise error(404, "SEMANTIC_ELEMENT_NOT_FOUND", "Semantic element not found", element_id=element_id)
    return found


def _normalise(element_type: str, property_name: str, value: Any) -> tuple[Any, str | None, str]:
    spec = PROPERTY_SPECS.get(element_type, {}).get(property_name)
    if spec is None:
        raise error(422, "PROPERTY_NOT_EDITABLE", "This semantic property is not editable", element_type=element_type,
                    property=property_name, allowed=sorted(PROPERTY_SPECS.get(element_type, {})))
    kind = spec["kind"]
    if kind == "string":
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 500:
            raise error(422, "INVALID_PROPERTY_VALUE", "Value must be a non-empty string of at most 500 characters",
                        property=property_name)
        normalised: Any = value.strip()
    elif kind == "integer":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or int(value) != value:
            raise error(422, "INVALID_PROPERTY_VALUE", "Value must be an integer", property=property_name)
        normalised = int(value)
    else:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise error(422, "INVALID_PROPERTY_VALUE", "Value must be a finite number", property=property_name)
        normalised = float(value)
    if "minimum" in spec and normalised < spec["minimum"]:
        raise error(422, "INVALID_PROPERTY_VALUE", "Value is below the supported minimum", property=property_name,
                    minimum=spec["minimum"])
    if "maximum" in spec and normalised > spec["maximum"]:
        raise error(422, "INVALID_PROPERTY_VALUE", "Value exceeds the supported maximum", property=property_name,
                    maximum=spec["maximum"])
    return normalised, spec["unit"], kind


def _typed(value: Any, unit: str | None, kind: str) -> dict[str, Any]:
    return {"value": value, "unit": unit, "data_type": kind}


def _quantity(value: Any, unit: str | None) -> dict[str, Any]:
    return {"value": value, "unit": unit}


def _resize_levels(model: dict[str, Any], count: int) -> None:
    old = {int(row["level_number"]): row for row in model.get("levels", [])}
    building = model.get("building") or {}
    f2f = building.get("floor_to_floor_height")
    f2f_value = f2f.get("value") if isinstance(f2f, dict) else None
    gfa = building.get("target_gfa")
    gfa_value = gfa.get("value") if isinstance(gfa, dict) else None
    project_id = str(model.get("project_id") or "")
    designer_state = model.get("designer_state") or {}
    overrides = designer_state.get("overrides", {})
    locks = designer_state.get("locks", {})
    fixed_area_by_number: dict[int, float] = {}
    unlocked_area_numbers: list[int] = []
    for number in range(1, count + 1):
        storey_id = _stable_id(project_id, "Storey", f"level:{number}")
        area_override = overrides.get(f"{storey_id}:area_m2")
        is_fixed = bool(locks.get(storey_id, {}).get("locked")) or area_override is not None
        old_area = old.get(number, {}).get("area")
        old_area_value = old_area.get("value") if isinstance(old_area, dict) else None
        fixed_value = area_override.get("value") if isinstance(area_override, dict) else old_area_value
        if is_fixed:
            if isinstance(fixed_value, (int, float)) and not isinstance(fixed_value, bool):
                fixed_area_by_number[number] = float(fixed_value)
        else:
            unlocked_area_numbers.append(number)
    remaining_gfa = float(gfa_value) - sum(fixed_area_by_number.values()) if gfa_value is not None else None
    distributable_area = (
        remaining_gfa / len(unlocked_area_numbers)
        if remaining_gfa is not None and remaining_gfa > 0 and unlocked_area_numbers else None
    )

    levels = []
    for number in range(1, count + 1):
        row = old.get(number, {"level_number": number, "name": f"Level {number}"})
        row["level_number"] = number
        row.setdefault("name", f"Level {number}")
        storey_id = _stable_id(project_id, "Storey", f"level:{number}")
        locked = bool(locks.get(storey_id, {}).get("locked"))
        if f2f_value is not None and not locked and f"{storey_id}:floor_to_floor_height_m" not in overrides:
            row["floor_to_floor_height"] = _quantity(float(f2f_value), "m")
        if gfa_value is not None and number in unlocked_area_numbers and distributable_area is not None:
            row["area"] = _quantity(distributable_area, "m2")
        levels.append(row)

    # Elevation is cumulative, not (level_number - 1) * a single global height.
    # Preserve locked storeys and explicit elevation overrides while reflowing the
    # unlocked storeys above them from each preceding storey's effective height.
    elevation = 0.0
    for row in levels:
        number = int(row["level_number"])
        storey_id = _stable_id(project_id, "Storey", f"level:{number}")
        locked = bool(locks.get(storey_id, {}).get("locked"))
        preserve_elevation = locked or f"{storey_id}:elevation_m" in overrides
        existing_elevation = row.get("elevation")
        existing_elevation_value = existing_elevation.get("value") if isinstance(existing_elevation, dict) else None
        if preserve_elevation and existing_elevation_value is not None:
            elevation = float(existing_elevation_value)
        else:
            row["elevation"] = _quantity(elevation, "m")
        height = row.get("floor_to_floor_height")
        height_value = height.get("value") if isinstance(height, dict) else f2f_value
        if height_value is not None:
            elevation += float(height_value)
    model["levels"] = levels


def _refresh_storey_area_consistency(model: dict[str, Any]) -> None:
    building = model.get("building") or {}
    target_gfa = building.get("target_gfa")
    target_value = target_gfa.get("value") if isinstance(target_gfa, dict) else None
    issues = [issue for issue in model.get("consistency_issues", [])
              if issue.get("code") != "STOREY_AREA_GFA_INCONSISTENCY"]
    levels = model.get("levels") or []
    areas = [
        (level.get("area") or {}).get("value")
        if isinstance(level.get("area"), dict) else None
        for level in levels
    ]
    if (target_value is not None and levels and all(value is not None for value in areas)
            and abs(sum(float(value) for value in areas) - float(target_value)) > max(1.0, float(target_value) * 0.01)):
        total = sum(float(value) for value in areas)
        issues.append({
            "code": "STOREY_AREA_GFA_INCONSISTENCY",
            "target_gfa_m2": float(target_value),
            "storey_area_total_m2": total,
            "message": "The sum of storey area values differs from the target GFA by more than 1%; review the locked or explicitly overridden floor areas.",
        })
    model["consistency_issues"] = issues


def _derived_building_height(model: dict[str, Any]) -> float | None:
    building = model.get("building") or {}
    levels = model.get("levels") or []
    level_heights = [
        (row.get("floor_to_floor_height") or {}).get("value")
        if isinstance(row.get("floor_to_floor_height"), dict) else None
        for row in levels
    ]
    if levels and all(value is not None for value in level_heights):
        return sum(float(value) for value in level_heights)
    floor_count = building.get("floor_count")
    floor_height = building.get("floor_to_floor_height")
    floor_height_value = floor_height.get("value") if isinstance(floor_height, dict) else None
    if floor_count is not None and floor_height_value is not None:
        return int(floor_count) * float(floor_height_value)
    return None


def apply_property(model: dict[str, Any], element: dict[str, Any], property_name: str,
                   value: Any, unit: str | None, kind: str) -> None:
    element_type = element["element_type"]
    identity_key = str(element.get("identity_key") or "")
    if element.get("designer_authored"):
        authored = next((item for item in model.get("designer_elements", []) if item.get("id") == element["id"]), None)
        if authored is None:
            raise error(409, "SEMANTIC_ELEMENT_MISSING", "Designer-authored element is no longer present")
        if property_name == "level_number":
            target_level = int(value)
            if not any(int(level["level_number"]) == target_level for level in model.get("levels", [])):
                raise error(422, "LEVEL_NOT_FOUND", "The requested storey does not exist", level_number=target_level)
            old_item = authored.get("properties", {}).get("level_number")
            old_level = old_item.get("value") if isinstance(old_item, dict) else None
            project_id = str(model["project_id"])
            for number in ({int(old_level), target_level} if old_level is not None else {target_level}):
                storey_id = _stable_id(project_id, "Storey", f"level:{number}")
                if (model.get("designer_state") or {}).get("locks", {}).get(storey_id, {}).get("locked"):
                    raise error(409, "LOCKED_DEPENDENCY", "A locked storey cannot have its hosted elements changed",
                                locked_element_id=storey_id, level_number=number)
            model["designer_relationships"] = [rel for rel in model.get("designer_relationships", [])
                if not (rel.get("target_id") == element["id"] and rel.get("relationship_type") in {"contains_space", "hosts_element"})]
            relationship_type = "contains_space" if element_type == "Space" else "hosts_element"
            model.setdefault("designer_relationships", []).append({
                "source_id": _stable_id(project_id, "Storey", f"level:{target_level}"),
                "relationship_type": relationship_type, "target_id": element["id"],
            })
        authored.setdefault("properties", {})[property_name] = _typed(value, unit, kind)
        authored.setdefault("provenance", {})[property_name] = {
            "source_type": "HUMAN_REVIEW", "source_id": element["id"], "confirmed": True,
        }
        return

    if element_type == "Site":
        site = model.setdefault("site", {})
        if property_name == "city":
            site.setdefault("location", {})["city"] = value
        else:
            key = {"area_m2": "area", "width_m": "width", "depth_m": "depth",
                   "orientation_deg": "orientation"}[property_name]
            site[key] = _quantity(value, unit)
    elif element_type == "Building":
        building = model.setdefault("building", {})
        mapping = {"use": ("use", None), "floor_count": ("floor_count", None),
                   "floor_to_floor_height_m": ("floor_to_floor_height", unit), "height_m": ("height", unit),
                   "target_gfa_m2": ("target_gfa", unit), "coverage_ratio": ("coverage", None)}
        count = int(value) if property_name == "floor_count" else None
        if count is not None:
            removed_numbers = {int(level["level_number"]) for level in model.get("levels", [])
                               if int(level["level_number"]) > count}
            project_id = str(model["project_id"])
            removed_storey_ids = {_stable_id(project_id, "Storey", f"level:{number}")
                                  for number in removed_numbers}
            locked_removed = sorted(element_id for element_id in removed_storey_ids
                                    if (model.get("designer_state") or {}).get("locks", {}).get(element_id, {}).get("locked"))
            if locked_removed:
                raise error(409, "LOCKED_DEPENDENCY", "Floor-count edit would remove a locked storey",
                            locked_element_ids=locked_removed, requested_floor_count=count)
            hosted_components = sorted({relationship.get("target_id") for relationship in model.get("designer_relationships", [])
                if relationship.get("source_id") in removed_storey_ids
                and relationship.get("relationship_type") in {"contains_space", "hosts_element"}})
            canonical_spaces = sorted(str(space.get("id") or space.get("name") or "")
                for space in model.get("spaces", []) if space.get("level_number") is not None
                and int(space["level_number"]) > count)
            if hosted_components or canonical_spaces:
                raise error(409, "STOREY_HAS_COMPONENTS",
                    "Move or remove spaces and designer-authored components before reducing the floor count",
                    element_ids=hosted_components, space_ids=canonical_spaces, requested_floor_count=count)
        if property_name in {"footprint_width_m", "footprint_depth_m"}:
            model.setdefault("properties", {})[property_name] = value
        else:
            key, quantity_unit = mapping[property_name]
            building[key] = _quantity(value, quantity_unit) if quantity_unit else value
        if count is not None:
            _resize_levels(model, count)
        elif property_name in {"floor_to_floor_height_m", "target_gfa_m2"}:
            existing_count = building.get("floor_count")
            if existing_count is not None and int(existing_count) >= 1:
                _resize_levels(model, int(existing_count))
    elif element_type == "Storey":
        try:
            number = int(identity_key.split(":", 1)[1])
        except (ValueError, IndexError):
            raise error(409, "SEMANTIC_ELEMENT_INVALID", "Storey identity is invalid") from None
        row = next((item for item in model.get("levels", []) if int(item["level_number"]) == number), None)
        if row is None:
            raise error(409, "SEMANTIC_ELEMENT_MISSING", "Storey no longer exists", level_number=number)
        mapping = {"elevation_m": "elevation", "floor_to_floor_height_m": "floor_to_floor_height", "area_m2": "area"}
        row[mapping[property_name]] = _quantity(value, unit)
    elif element_type == "ParkingFacility":
        parking = model.setdefault("parking", {})
        parking["spaces" if property_name == "spaces" else "arrangement"] = (
            _quantity(value, unit) if property_name == "spaces" else value)
    elif element_type == "Space":
        space = next((item for item in model.get("spaces", [])
                      if str(item.get("id") or item.get("name") or "") == identity_key), None)
        if space is None:
            raise error(409, "SEMANTIC_ELEMENT_MISSING", "Space no longer exists", identity_key=identity_key)
        if property_name == "level_number":
            target_level = int(value)
            if not any(int(level["level_number"]) == target_level for level in model.get("levels", [])):
                raise error(422, "LEVEL_NOT_FOUND", "The requested storey does not exist", level_number=target_level)
            target_storey_id = _stable_id(str(model["project_id"]), "Storey", f"level:{target_level}")
            semantic = model.get("semantic_model") or compile_semantic_model(model)
            locked_target = locked_ancestor_for(semantic, model.get("designer_state") or initial_designer_state(),
                                                target_storey_id)
            if locked_target is not None:
                raise error(409, "LOCKED_DEPENDENCY", "Cannot move a space into a locked storey",
                            locked_element_id=locked_target, level_number=target_level)
        mapping = {"use": "use", "area_m2": "area", "level_number": "level_number"}
        key = mapping[property_name]
        space[key] = _quantity(value, unit) if property_name == "area_m2" else value
    else:
        raise error(422, "PROPERTY_NOT_EDITABLE", "This semantic element cannot be edited", element_type=element_type)

    model.setdefault("provenance", {})[f"designer:{element['id']}:{property_name}"] = {
        "source_type": "HUMAN_REVIEW", "source_id": element["id"], "confirmed": True,
    }
    if element_type == "Building" and property_name in {"floor_count", "floor_to_floor_height_m", "height_m"}:
        building = model.get("building") or {}
        floors = building.get("floor_count")
        f2f = building.get("floor_to_floor_height")
        height = building.get("height")
        f2f_value = f2f.get("value") if isinstance(f2f, dict) else None
        height_value = height.get("value") if isinstance(height, dict) else None
        height_provenance = model.get("provenance", {}).get("building_height", {})
        height_override_key = f"{_stable_id(str(model['project_id']), 'Building', 'building')}:height_m"
        has_explicit_designer_height = height_override_key in (model.get("designer_state") or {}).get("overrides", {})
        derived_height = _derived_building_height(model)
        if (property_name in {"floor_count", "floor_to_floor_height_m"}
                and height_provenance.get("source_type") == "DERIVED"
                and not has_explicit_designer_height and derived_height is not None):
            building["height"] = _quantity(derived_height, "m")
            height_value = derived_height
        issues = [issue for issue in model.get("consistency_issues", [])
                  if issue.get("code") != "HEIGHT_FLOOR_INCONSISTENCY"]
        if derived_height is not None and height_value is not None and abs(float(height_value) - derived_height) > 0.5:
            issues.append({"code": "HEIGHT_FLOOR_INCONSISTENCY", "explicit_height_m": float(height_value),
                           "derived_height_m": derived_height, "floor_count": int(floors) if floors is not None else None,
                           "floor_to_floor_m": float(f2f_value) if f2f_value is not None else None})
        model["consistency_issues"] = issues
    # Designer-authored values override extraction/assumption values in a way that
    # survives canonical World Model rebuilds for this project version.
    if element_type in {"Site", "Building", "Storey", "Space", "ParkingFacility"}:
        state = model.setdefault("designer_state", initial_designer_state())
        state.setdefault("overrides", {})[f"{element['id']}:{property_name}"] = {
            "element_id": element["id"], "element_type": element_type, "identity_key": identity_key,
            "property": property_name, "value": value, "unit": unit, "data_type": kind,
        }
    if element_type == "Storey" and property_name == "floor_to_floor_height_m":
        _resize_levels(model, len(model.get("levels", [])))
        building = model.get("building") or {}
        height_provenance = model.get("provenance", {}).get("building_height", {})
        height_override_key = f"{_stable_id(str(model['project_id']), 'Building', 'building')}:height_m"
        has_explicit_designer_height = height_override_key in (model.get("designer_state") or {}).get("overrides", {})
        derived_height = _derived_building_height(model)
        if (height_provenance.get("source_type") == "DERIVED"
                and not has_explicit_designer_height and derived_height is not None):
            building["height"] = _quantity(derived_height, "m")
        height = building.get("height")
        height_value = height.get("value") if isinstance(height, dict) else None
        issues = [issue for issue in model.get("consistency_issues", [])
                  if issue.get("code") != "HEIGHT_FLOOR_INCONSISTENCY"]
        if derived_height is not None and height_value is not None and abs(float(height_value) - derived_height) > 0.5:
            issues.append({"code": "HEIGHT_FLOOR_INCONSISTENCY", "explicit_height_m": float(height_value),
                           "derived_height_m": derived_height, "floor_count": building.get("floor_count"),
                           "floor_to_floor_m": (building.get("floor_to_floor_height") or {}).get("value")})
        model["consistency_issues"] = issues
    _refresh_storey_area_consistency(model)


def _semantic_ids_without_relationship_validation(model: dict[str, Any]) -> set[str]:
    project_id = str(model.get("project_id") or "")
    ids = {
        _stable_id(project_id, "Site", "site"),
        _stable_id(project_id, "Building", "building"),
    }
    levels = model.get("levels") or []
    ids.update(_stable_id(project_id, "Storey", f"level:{int(level['level_number'])}") for level in levels)
    elements_count = 2 + len(levels)
    for index, space in enumerate(model.get("spaces") or []):
        key = str(space.get("id") or space.get("name") or elements_count + index)
        ids.add(_stable_id(project_id, "Space", key))
    parking = model.get("parking") or {}
    if parking.get("arrangement") is not None or parking.get("spaces") is not None:
        ids.add(_stable_id(project_id, "ParkingFacility", "parking"))
    ids.update(str(item.get("id")) for item in model.get("designer_elements") or [] if item.get("id"))
    return ids


def apply_overrides(model: dict[str, Any], state: dict[str, Any]) -> None:
    # Validate locks and authored relationships before compiling the graph. A
    # requirement rebuild can remove Storeys; compilation must return a typed
    # conflict instead of throwing an unhandled error or orphaning components.
    model["designer_state"] = copy.deepcopy(state)
    model.setdefault("designer_elements", [])
    model.setdefault("designer_relationships", [])
    present_ids = _semantic_ids_without_relationship_validation(model)
    removed_locked_ids = sorted(element_id for element_id, info in state.get("locks", {}).items()
                                if info.get("locked") and element_id not in present_ids)
    if removed_locked_ids:
        raise error(409, "LOCKED_DEPENDENCY",
                    "The World Model rebuild would remove one or more locked semantic elements",
                    locked_element_ids=removed_locked_ids)
    stale_relationships = [
        relationship for relationship in model.get("designer_relationships", [])
        if relationship.get("source_id") not in present_ids or relationship.get("target_id") not in present_ids
    ]
    if stale_relationships:
        raise error(409, "STOREY_HAS_COMPONENTS",
                    "The World Model rebuild would orphan designer-authored components; move or remove them before changing requirements",
                    relationships=stale_relationships)
    floor_count = (model.get("building") or {}).get("floor_count")
    if isinstance(floor_count, int) and not isinstance(floor_count, bool) and 1 <= floor_count <= 100:
        _resize_levels(model, floor_count)
        present_ids = _semantic_ids_without_relationship_validation(model)
        removed_locked_ids = sorted(element_id for element_id, info in state.get("locks", {}).items()
                                    if info.get("locked") and element_id not in present_ids)
        if removed_locked_ids:
            raise error(409, "LOCKED_DEPENDENCY",
                        "The World Model rebuild would remove one or more locked semantic elements",
                        locked_element_ids=removed_locked_ids)
        stale_relationships = [
            relationship for relationship in model.get("designer_relationships", [])
            if relationship.get("source_id") not in present_ids or relationship.get("target_id") not in present_ids
        ]
        if stale_relationships:
            raise error(409, "STOREY_HAS_COMPONENTS",
                        "The World Model rebuild would orphan designer-authored components; move or remove them before changing requirements",
                        relationships=stale_relationships)
    override_items = list(state.get("overrides", {}).values())
    # Apply floor-count overrides first so removed storeys are detected before
    # any older per-storey override can be applied to a now-obsolete entity.
    override_items.sort(key=lambda item: 0 if item.get("element_type") == "Building"
                       and item.get("property") == "floor_count" else 1)
    for override in override_items:
        semantic = compile_semantic_model(model)
        model["semantic_model"] = semantic
        element = next((item for item in semantic["elements"] if item.get("id") == override.get("element_id")), None)
        if element is None:
            model.setdefault("consistency_issues", []).append({
                "code": "DESIGNER_OVERRIDE_REVIEW_REQUIRED",
                "element_id": override.get("element_id"),
                "property": override.get("property"),
                "reason": "The overridden semantic element no longer exists after upstream constraints changed.",
            })
            continue
        try:
            apply_property(model, element, override["property"], override["value"], override.get("unit"),
                           override.get("data_type", "number"))
        except Exception as exc:
            # A previously valid override can become inapplicable when an
            # upstream constraint changes (for example a removed storey). Keep
            # the canonical rebuild healthy and surface the conflict as explicit
            # review data rather than silently discarding it.
            from fastapi import HTTPException
            if not isinstance(exc, HTTPException) or exc.status_code not in {404, 409, 422}:
                raise
            model.setdefault("consistency_issues", []).append({
                "code": "DESIGNER_OVERRIDE_REVIEW_REQUIRED",
                "element_id": override.get("element_id"),
                "property": override.get("property"),
                "reason": str(exc.detail),
            })
    building = model.get("building") or {}
    derived_height = _derived_building_height(model)
    height_override_key = f"{_stable_id(str(model['project_id']), 'Building', 'building')}:height_m"
    height_provenance = model.get("provenance", {}).get("building_height", {})
    has_explicit_designer_height = height_override_key in state.get("overrides", {})
    if (derived_height is not None and height_provenance.get("source_type") == "DERIVED"
            and not has_explicit_designer_height):
        building["height"] = _quantity(derived_height, "m")
    height = building.get("height")
    height_value = height.get("value") if isinstance(height, dict) else None
    issues = [issue for issue in model.get("consistency_issues", [])
              if issue.get("code") != "HEIGHT_FLOOR_INCONSISTENCY"]
    if derived_height is not None and height_value is not None and abs(float(height_value) - derived_height) > 0.5:
        issues.append({"code": "HEIGHT_FLOOR_INCONSISTENCY", "explicit_height_m": float(height_value),
                       "derived_height_m": derived_height, "floor_count": building.get("floor_count"),
                       "floor_to_floor_m": (building.get("floor_to_floor_height") or {}).get("value")})
    model["consistency_issues"] = issues
    _refresh_storey_area_consistency(model)
    model["semantic_model"] = compile_semantic_model(model)


def _append_event(state: dict[str, Any], *, action: str, actor_id: str, element_id: str | None,
                  details: dict[str, Any]) -> dict[str, Any]:
    event = {"event_id": str(uuid4()), "action": action, "actor_id": actor_id, "element_id": element_id,
             "created_at": now_iso(), **copy.deepcopy(details)}
    state.setdefault("history", []).append(event)
    return event


def _authored(model: dict[str, Any], element_id: str) -> dict[str, Any] | None:
    return next((item for item in model.get("designer_elements", []) if item.get("id") == element_id), None)


def _unset_property(model: dict[str, Any], element: dict[str, Any], property_name: str) -> None:
    element_type = element["element_type"]
    identity_key = str(element.get("identity_key") or "")
    if element.get("designer_authored"):
        authored = _authored(model, element["id"])
        if authored:
            authored.setdefault("properties", {}).pop(property_name, None)
        return
    if element_type == "Building" and property_name in {"footprint_width_m", "footprint_depth_m"}:
        model.setdefault("properties", {}).pop(property_name, None)
    elif element_type == "Site":
        if property_name == "city":
            model.setdefault("site", {}).setdefault("location", {}).pop("city", None)
        else:
            key = {"area_m2": "area", "width_m": "width", "depth_m": "depth", "orientation_deg": "orientation"}[property_name]
            model.setdefault("site", {})[key] = None
    elif element_type == "Building":
        key = {"use": "use", "floor_count": "floor_count", "floor_to_floor_height_m": "floor_to_floor_height",
               "height_m": "height", "target_gfa_m2": "target_gfa", "coverage_ratio": "coverage"}[property_name]
        model.setdefault("building", {})[key] = None
        if property_name == "floor_count":
            model["levels"] = []
    elif element_type == "Storey":
        number = int(identity_key.split(":", 1)[1])
        row = next((item for item in model.get("levels", []) if int(item["level_number"]) == number), None)
        if row:
            row[{"elevation_m": "elevation", "floor_to_floor_height_m": "floor_to_floor_height", "area_m2": "area"}[property_name]] = None
    elif element_type == "ParkingFacility":
        model.setdefault("parking", {})["spaces" if property_name == "spaces" else "arrangement"] = None
    elif element_type == "Space":
        space = next((item for item in model.get("spaces", []) if str(item.get("id") or item.get("name") or "") == identity_key), None)
        if space:
            space[{"use": "use", "area_m2": "area", "level_number": "level_number"}[property_name]] = None
    state = model.setdefault("designer_state", initial_designer_state())
    state.setdefault("overrides", {}).pop(f"{element['id']}:{property_name}", None)
    model.setdefault("provenance", {}).pop(f"designer:{element['id']}:{property_name}", None)


def _apply_entity_event(model: dict[str, Any], event: dict[str, Any], *, forward: bool) -> None:
    action = event["action"]
    snapshot = event.get("after") if forward else event.get("before")
    element_id = event.get("element_id")
    if action == "EDIT":
        semantic = compile_semantic_model(model)
        element = next((item for item in semantic["elements"] if item["id"] == element_id), None)
        if element is None:
            raise error(409, "UNDO_TARGET_MISSING", "The edited semantic element no longer exists", element_id=element_id)
        target = event.get("after") if forward else event.get("before")
        if target is None:
            _unset_property(model, element, event["property"])
        else:
            normalised, unit, kind = _normalise(element["element_type"], event["property"], target)
            apply_property(model, element, event["property"], normalised, unit, kind)
        if not event.get("designer_authored"):
            override_key = f"{element_id}:{event['property']}"
            target_override = event.get("after_override") if forward else event.get("before_override")
            if target_override is None:
                model.setdefault("designer_state", initial_designer_state()).setdefault("overrides", {}).pop(override_key, None)
                model.setdefault("provenance", {}).pop(f"designer:{element_id}:{event['property']}", None)
            else:
                model.setdefault("designer_state", initial_designer_state()).setdefault("overrides", {})[override_key] = copy.deepcopy(target_override)
    elif action == "CREATE":
        if forward:
            if _authored(model, element_id) is None:
                model.setdefault("designer_elements", []).append(copy.deepcopy(snapshot["element"]))
                model.setdefault("designer_relationships", []).extend(copy.deepcopy(snapshot.get("relationships", [])))
        else:
            model["designer_elements"] = [item for item in model.get("designer_elements", []) if item.get("id") != element_id]
            model["designer_relationships"] = [r for r in model.get("designer_relationships", [])
                if r.get("source_id") != element_id and r.get("target_id") != element_id]
    elif action == "DELETE":
        if forward:
            model["designer_elements"] = [item for item in model.get("designer_elements", []) if item.get("id") != element_id]
            model["designer_relationships"] = [r for r in model.get("designer_relationships", [])
                if r.get("source_id") != element_id and r.get("target_id") != element_id]
        elif _authored(model, element_id) is None:
            model.setdefault("designer_elements", []).append(copy.deepcopy(snapshot["element"]))
            model.setdefault("designer_relationships", []).extend(copy.deepcopy(snapshot.get("relationships", [])))
    elif action == "HOST_CHANGE":
        _apply_host_relationship(model, model.get("designer_state") or initial_designer_state(),
                                 element_id, event.get("after") if forward else event.get("before"))


def edit_property(model: dict[str, Any], state: dict[str, Any], element_id: str, property_name: str,
                  value: Any, actor_id: str, reason: str) -> dict[str, Any]:
    element = _element(model, element_id)
    _assert_element_editable(model, state, element)
    new_value, unit, kind = _normalise(element["element_type"], property_name, value)
    current = element.get("properties", {}).get(property_name)
    before = current.get("value") if isinstance(current, dict) else None
    override_key = f"{element_id}:{property_name}"
    before_override = copy.deepcopy(state.get("overrides", {}).get(override_key))
    if before == new_value:
        raise error(409, "NO_CHANGE", "The requested value is already current", element_id=element_id,
                    property=property_name)
    apply_property(model, element, property_name, new_value, unit, kind)
    after_override = copy.deepcopy(state.get("overrides", {}).get(override_key))
    event = _append_event(state, action="EDIT", actor_id=actor_id, element_id=element_id,
        details={"element_type": element["element_type"], "identity_key": element.get("identity_key"),
                 "property": property_name, "before": before, "after": new_value, "unit": unit,
                 "before_override": before_override, "after_override": after_override,
                 "designer_authored": bool(element.get("designer_authored")),
                 "reason": reason, "impacts": impact_groups(element["element_type"], property_name)})
    state.setdefault("undo_stack", []).append(event["event_id"])
    state["redo_stack"] = []
    model["designer_state"] = state
    model["semantic_model"] = compile_semantic_model(model)
    return event


def locked_ancestor_for(semantic: dict[str, Any], state: dict[str, Any], element_id: str) -> str | None:
    """Find the first locked element in this element's containing chain."""
    locked = {key for key, info in state.get("locks", {}).items() if info.get("locked")}
    parents: dict[str, set[str]] = {}
    for relationship in semantic.get("relationships", []):
        source, target, kind = relationship["source_id"], relationship["target_id"], relationship["relationship_type"]
        parent, child = (target, source) if kind == "located_on" else (source, target)
        parents.setdefault(child, set()).add(parent)
    seen: set[str] = set()
    frontier = [element_id]
    while frontier:
        current = frontier.pop(0)
        if current in seen:
            continue
        seen.add(current)
        if current in locked:
            return current
        frontier.extend(sorted(parents.get(current, set()) - seen))
    return None


def downstream_elements_for_scope(semantic: dict[str, Any], element_id: str) -> set[str]:
    """Return the selected element and its transitive descendants, excluding ancestors/siblings."""
    children: dict[str, set[str]] = {}
    for relationship in semantic.get("relationships", []):
        source, target, kind = relationship["source_id"], relationship["target_id"], relationship["relationship_type"]
        parent, child = (target, source) if kind == "located_on" else (source, target)
        children.setdefault(parent, set()).add(child)
    downstream = {element_id}
    frontier = [element_id]
    while frontier:
        current = frontier.pop()
        for child in children.get(current, set()):
            if child not in downstream:
                downstream.add(child)
                frontier.append(child)
    return downstream


def affected_elements_for_scope(semantic: dict[str, Any], element_id: str) -> set[str]:
    """Return the target, its transitive descendants, and its ancestor chain without siblings."""
    children: dict[str, set[str]] = {}
    parents: dict[str, set[str]] = {}
    for relationship in semantic.get("relationships", []):
        source, target, kind = relationship["source_id"], relationship["target_id"], relationship["relationship_type"]
        parent, child = (target, source) if kind == "located_on" else (source, target)
        children.setdefault(parent, set()).add(child)
        parents.setdefault(child, set()).add(parent)

    affected = {element_id}
    # Downstream dependents of the selected element (e.g. doors/windows hosted by a wall).
    frontier = [element_id]
    while frontier:
        current = frontier.pop()
        for child in children.get(current, set()):
            if child not in affected:
                affected.add(child)
                frontier.append(child)
    # Include ancestors for aggregate quantities and feasibility propagation, but do
    # not walk back down from an ancestor (which would incorrectly include siblings).
    frontier = [element_id]
    visited: set[str] = set()
    while frontier:
        current = frontier.pop()
        for parent in parents.get(current, set()):
            if parent not in visited:
                visited.add(parent)
                affected.add(parent)
                frontier.append(parent)
    return affected


def protected_elements_for_scope(semantic: dict[str, Any], state: dict[str, Any], element_ids: set[str]) -> set[str]:
    """Return targets protected by a direct lock or any locked semantic ancestor."""
    return {element_id for element_id in element_ids
            if locked_ancestor_for(semantic, state, element_id) is not None}


def _assert_element_editable(model: dict[str, Any], state: dict[str, Any], element: dict[str, Any]) -> None:
    semantic = model.get("semantic_model") or compile_semantic_model(model)
    locked_ancestor = locked_ancestor_for(semantic, state, element["id"])
    if locked_ancestor is not None:
        lock = state.get("locks", {}).get(locked_ancestor, {})
        raise error(409, "ELEMENT_LOCKED", "This element or one of its containing elements is locked",
                    element_id=element["id"], locked_ancestor_id=locked_ancestor, reason=lock.get("reason"))

def impact_groups(element_type: str, property_name: str) -> list[str]:
    if property_name in {"city", "orientation_deg", "coverage_ratio"}:
        return ["feasibility", "regulatory_review", "design_alternatives", "validation"]
    if property_name in {"use"}:
        return ["design_alternatives", "quantities", "cost", "structural_review", "regulatory_review", "validation"]
    if element_type in {"Wall", "Slab", "Roof", "Door", "Window", "Space"} or property_name in {
        "footprint_width_m", "footprint_depth_m", "width_m", "depth_m", "length_m", "thickness_m",
        "elevation_m", "level_number",
    }:
        return ["parametric_geometry_intents", "quantities", "cost", "validation"]
    if property_name in {"area_m2", "target_gfa_m2", "floor_count", "floor_to_floor_height_m",
                         "height_m", "spaces", "arrangement"}:
        return ["design_alternatives", "parametric_geometry_intents", "quantities", "cost",
                "structural_review", "regulatory_review", "validation"]
    return ["design_alternatives", "parametric_geometry_intents", "validation"]


def set_lock(state: dict[str, Any], element_id: str, actor_id: str, locked: bool, reason: str) -> dict[str, Any]:
    if locked:
        state.setdefault("locks", {})[element_id] = {"locked": True, "reason": reason,
            "locked_by": actor_id, "updated_at": now_iso()}
    else:
        state.setdefault("locks", {}).pop(element_id, None)
    return _append_event(state, action="LOCK" if locked else "UNLOCK", actor_id=actor_id,
                         element_id=element_id, details={"reason": reason})


def create_element(model: dict[str, Any], state: dict[str, Any], *, element_type: str, name: str,
                   properties: dict[str, Any], level_number: int | None, actor_id: str, reason: str,
                   host_element_id: str | None = None) -> dict[str, Any]:
    if element_type not in CREATABLE_TYPES:
        raise error(422, "ELEMENT_TYPE_NOT_CREATABLE", "Only spaces and explicit architectural components can be authored",
                    allowed=sorted(CREATABLE_TYPES))
    if element_type not in CAD_MAPPINGS:
        raise error(422, "ELEMENT_TYPE_UNSUPPORTED", "No semantic-to-CAD mapping exists for this element type")
    if host_element_id and element_type not in {"Door", "Window"}:
        raise error(422, "INVALID_ELEMENT_HOST", "Only doors and windows accept a host_element_id")
    if not name.strip() or len(name.strip()) > 120:
        raise error(422, "INVALID_ELEMENT_NAME", "Element name must contain 1–120 characters")
    if len(properties) > 30:
        raise error(422, "TOO_MANY_PROPERTIES", "An element can contain at most 30 properties")
    element_id = str(uuid4())
    identity_key = f"designer:{element_id}"
    typed: dict[str, Any] = {}
    for key, value in properties.items():
        normalised, unit, kind = _normalise(element_type, key, value)
        typed[key] = _typed(normalised, unit, kind)
    if level_number is None and "level_number" in properties:
        raw_level = properties["level_number"]
        if isinstance(raw_level, int) and not isinstance(raw_level, bool):
            level_number = raw_level
    # A door/window inherits placement from its host wall; an independent storey
    # assignment would create contradictory spatial relationships.
    if element_type in {"Door", "Window"} and host_element_id:
        level_number = None
        typed.pop("level_number", None)

    project_id = str(model["project_id"])
    building_id = _stable_id(project_id, "Building", "building")
    semantic_before = model.get("semantic_model") or compile_semantic_model(model)
    locked_building = locked_ancestor_for(semantic_before, state, building_id)
    if locked_building is not None:
        raise error(409, "LOCKED_DEPENDENCY", "Cannot add a component inside a locked building",
                    locked_element_id=locked_building)
    if level_number is not None:
        if level_number < 1:
            raise error(422, "INVALID_LEVEL", "level_number must be positive")
        if not any(int(level["level_number"]) == level_number for level in model.get("levels", [])):
            raise error(422, "LEVEL_NOT_FOUND", "The requested storey does not exist", level_number=level_number)
        storey_id = _stable_id(project_id, "Storey", f"level:{level_number}")
        locked_storey = locked_ancestor_for(semantic_before, state, storey_id)
        if locked_storey is not None:
            raise error(409, "LOCKED_DEPENDENCY", "Cannot add an element to a locked storey",
                        locked_element_id=locked_storey, level_number=level_number)
        if "level_number" in PROPERTY_SPECS[element_type]:
            typed["level_number"] = _typed(level_number, "count", "integer")
    if element_type in {"Door", "Window"} and host_element_id:
        host = _element(model, host_element_id)
        if host["element_type"] != "Wall":
            raise error(422, "INVALID_OPENING_HOST", "Doors and windows must be hosted by a Wall semantic element",
                        host_element_id=host_element_id, host_element_type=host["element_type"])
        locked_host = locked_ancestor_for(semantic_before, state, host_element_id)
        if locked_host is not None:
            raise error(409, "LOCKED_DEPENDENCY", "Cannot add an opening to a locked host wall",
                        locked_element_id=locked_host)

    authored = {"id": element_id, "identity_key": identity_key, "element_type": element_type,
                "name": name.strip(), "properties": typed, "provenance": {
                    "created": {"source_type": "HUMAN_REVIEW", "source_id": actor_id, "confirmed": True}},
                "created_by": actor_id, "created_at": now_iso()}
    relationships: list[dict[str, Any]] = []
    if element_type in {"Door", "Window"} and host_element_id:
        relationships.append({"source_id": host_element_id, "relationship_type": "hosts_opening", "target_id": element_id})
    elif level_number is not None:
        storey_id = _stable_id(project_id, "Storey", f"level:{level_number}")
        relationship_type = "contains_space" if element_type == "Space" else "hosts_element"
        relationships.append({"source_id": storey_id, "relationship_type": relationship_type, "target_id": element_id})
    else:
        relationships.append({"source_id": building_id, "relationship_type": "contains_element", "target_id": element_id})
    model.setdefault("designer_elements", []).append(authored)
    model.setdefault("designer_relationships", []).extend(relationships)
    event = _append_event(state, action="CREATE", actor_id=actor_id, element_id=element_id,
        details={"element_type": element_type, "reason": reason,
                 "before": None, "after": {"element": copy.deepcopy(authored), "relationships": copy.deepcopy(relationships)}})
    state.setdefault("undo_stack", []).append(event["event_id"])
    state["redo_stack"] = []
    model["designer_state"] = state
    model["semantic_model"] = compile_semantic_model(model)
    return event


def _apply_host_relationship(model: dict[str, Any], state: dict[str, Any], element_id: str,
                            host_element_id: str | None) -> None:
    element = _element(model, element_id)
    if element["element_type"] not in {"Door", "Window"} or not element.get("designer_authored"):
        raise error(422, "HOST_RELATIONSHIP_NOT_EDITABLE", "Only designer-authored doors and windows can change wall hosts")
    _assert_element_editable(model, state, element)
    if host_element_id:
        host = _element(model, host_element_id)
        if host["element_type"] != "Wall":
            raise error(422, "INVALID_OPENING_HOST", "Doors and windows must be hosted by a Wall semantic element",
                        host_element_id=host_element_id, host_element_type=host["element_type"])
        _assert_element_editable(model, state, host)

    old_host_id = next((relationship["source_id"] for relationship in model.get("designer_relationships", [])
                        if relationship.get("target_id") == element_id
                        and relationship.get("relationship_type") == "hosts_opening"), None)
    if old_host_id == host_element_id:
        raise error(409, "NO_CHANGE", "The requested wall host is already current", element_id=element_id)

    relationships = model.setdefault("designer_relationships", [])
    placement: dict[str, Any] | None = None
    if old_host_id:
        host_parent = next((relationship for relationship in relationships
                            if relationship.get("target_id") == old_host_id
                            and relationship.get("relationship_type") in {"hosts_element", "contains_element"}), None)
        if host_parent:
            parent_id = host_parent["source_id"]
            parent_type = next((item["element_type"] for item in (model.get("semantic_model") or {}).get("elements", [])
                                if item["id"] == parent_id), None)
            relationship_type = "hosts_element" if parent_type == "Storey" else "contains_element"
            placement = {"source_id": parent_id, "relationship_type": relationship_type, "target_id": element_id}
    relationships[:] = [relationship for relationship in relationships
        if not (relationship.get("target_id") == element_id
                and relationship.get("relationship_type") in {"hosts_opening", "hosts_element", "contains_element"})]
    if host_element_id:
        relationships.append({"source_id": host_element_id, "relationship_type": "hosts_opening", "target_id": element_id})
    else:
        if placement is None:
            building_id = _stable_id(str(model["project_id"]), "Building", "building")
            placement = {"source_id": building_id, "relationship_type": "contains_element", "target_id": element_id}
        relationships.append(placement)


def set_host(model: dict[str, Any], state: dict[str, Any], element_id: str, host_element_id: str | None,
             actor_id: str, reason: str) -> dict[str, Any]:
    element = _element(model, element_id)
    old_host_id = next((relationship["source_id"] for relationship in model.get("designer_relationships", [])
                        if relationship.get("target_id") == element_id
                        and relationship.get("relationship_type") == "hosts_opening"), None)
    if old_host_id == host_element_id:
        raise error(409, "NO_CHANGE", "The requested wall host is already current", element_id=element_id)
    _apply_host_relationship(model, state, element_id, host_element_id)
    event = _append_event(state, action="HOST_CHANGE", actor_id=actor_id, element_id=element_id,
        details={"element_type": element["element_type"], "before": old_host_id, "after": host_element_id,
                 "reason": reason, "impacts": impact_groups(element["element_type"], "host_element_id")})
    state.setdefault("undo_stack", []).append(event["event_id"])
    state["redo_stack"] = []
    model["designer_state"] = state
    model["semantic_model"] = compile_semantic_model(model)
    return event


def delete_element(model: dict[str, Any], state: dict[str, Any], element_id: str, actor_id: str, reason: str) -> dict[str, Any]:
    element = _element(model, element_id)
    if not element.get("designer_authored"):
        raise error(409, "CANONICAL_ELEMENT_PROTECTED", "Canonical Site, Building, and Storey entities cannot be deleted")
    _assert_element_editable(model, state, element)
    authored = _authored(model, element_id)
    dependents = sorted(r.get("target_id") for r in model.get("designer_relationships", [])
                       if r.get("source_id") == element_id and r.get("relationship_type") == "hosts_opening")
    if dependents:
        raise error(409, "ELEMENT_HAS_DEPENDENTS", "Remove hosted doors/windows before deleting this wall",
                    dependent_element_ids=dependents)
    relationships = [r for r in model.get("designer_relationships", [])
                     if r.get("source_id") == element_id or r.get("target_id") == element_id]
    for relationship in relationships:
        if relationship.get("target_id") == element_id and relationship.get("relationship_type") in {"contains_space", "hosts_element"}:
            storey_id = relationship.get("source_id")
            if state.get("locks", {}).get(storey_id, {}).get("locked"):
                raise error(409, "LOCKED_DEPENDENCY", "Cannot delete an element hosted by a locked storey",
                            locked_element_id=storey_id)
    if authored is None:
        raise error(404, "SEMANTIC_ELEMENT_NOT_FOUND", "Designer-authored element not found")
    model["designer_elements"] = [item for item in model.get("designer_elements", []) if item.get("id") != element_id]
    model["designer_relationships"] = [r for r in model.get("designer_relationships", [])
        if r.get("source_id") != element_id and r.get("target_id") != element_id]
    state.get("locks", {}).pop(element_id, None)
    event = _append_event(state, action="DELETE", actor_id=actor_id, element_id=element_id,
        details={"element_type": element["element_type"], "reason": reason,
                 "before": {"element": copy.deepcopy(authored), "relationships": copy.deepcopy(relationships)}, "after": None})
    state.setdefault("undo_stack", []).append(event["event_id"])
    state["redo_stack"] = []
    model["designer_state"] = state
    model["semantic_model"] = compile_semantic_model(model)
    return event


def undo(model: dict[str, Any], state: dict[str, Any], actor_id: str) -> dict[str, Any]:
    stack = state.setdefault("undo_stack", [])
    if not stack:
        raise error(409, "UNDO_EMPTY", "There are no designer edits to undo")
    event_id = stack[-1]
    event = next((item for item in state.get("history", []) if item.get("event_id") == event_id), None)
    if event is None:
        raise error(409, "UNDO_HISTORY_INVALID", "Undo history is inconsistent")
    element_id = event.get("element_id")
    if element_id and event.get("action") in {"EDIT", "HOST_CHANGE"}:
        element = _element(model, element_id)
        _assert_element_editable(model, state, element)
    if event.get("action") in {"CREATE", "DELETE"}:
        if element_id and state.get("locks", {}).get(element_id, {}).get("locked"):
            raise error(409, "ELEMENT_LOCKED", "Undo is blocked because the target element is locked",
                        element_id=element_id)
        snapshots = [event.get("before"), event.get("after")]
        related_ids = {rel.get("source_id") for snapshot in snapshots if snapshot
                       for rel in snapshot.get("relationships", [])}
        semantic = model.get("semantic_model") or compile_semantic_model(model)
        locked_related = sorted(protected_elements_for_scope(semantic, state, related_ids))
        if locked_related:
            raise error(409, "LOCKED_DEPENDENCY", "Undo is blocked by a locked containing element",
                        locked_element_ids=locked_related)
    _apply_entity_event(model, event, forward=False)
    stack.pop()
    state.setdefault("redo_stack", []).append(event_id)
    undo_event = _append_event(state, action="UNDO", actor_id=actor_id, element_id=element_id,
                               details={"target_event_id": event_id})
    model["designer_state"] = state
    model["semantic_model"] = compile_semantic_model(model)
    return undo_event


def redo(model: dict[str, Any], state: dict[str, Any], actor_id: str) -> dict[str, Any]:
    stack = state.setdefault("redo_stack", [])
    if not stack:
        raise error(409, "REDO_EMPTY", "There are no designer edits to redo")
    event_id = stack[-1]
    event = next((item for item in state.get("history", []) if item.get("event_id") == event_id), None)
    if event is None:
        raise error(409, "REDO_HISTORY_INVALID", "Redo history is inconsistent")
    element_id = event.get("element_id")
    if element_id and event.get("action") in {"EDIT", "HOST_CHANGE"}:
        element = _element(model, element_id)
        _assert_element_editable(model, state, element)
    if event.get("action") in {"CREATE", "DELETE"}:
        if element_id and state.get("locks", {}).get(element_id, {}).get("locked"):
            raise error(409, "ELEMENT_LOCKED", "Undo is blocked because the target element is locked",
                        element_id=element_id)
        snapshots = [event.get("before"), event.get("after")]
        related_ids = {rel.get("source_id") for snapshot in snapshots if snapshot
                       for rel in snapshot.get("relationships", [])}
        semantic = model.get("semantic_model") or compile_semantic_model(model)
        locked_related = sorted(protected_elements_for_scope(semantic, state, related_ids))
        if locked_related:
            raise error(409, "LOCKED_DEPENDENCY", "Redo is blocked by a locked containing element",
                        locked_element_ids=locked_related)
    _apply_entity_event(model, event, forward=True)
    stack.pop()
    state.setdefault("undo_stack", []).append(event_id)
    redo_event = _append_event(state, action="REDO", actor_id=actor_id, element_id=element_id,
                               details={"target_event_id": event_id})
    model["designer_state"] = state
    model["semantic_model"] = compile_semantic_model(model)
    return redo_event


def _stable_id(project_id: str, element_type: str, key: str) -> str:
    from uuid import NAMESPACE_URL, uuid5
    return str(uuid5(NAMESPACE_URL, f"airchitect:{project_id}:{element_type}:{key}"))


async def persist_designer_mutation(session: AsyncSession, *, project: Project, version: ProjectVersion,
                                    user: User, model: dict[str, Any], action: str,
                                    event: dict[str, Any] | None = None,
                                    commit: bool = True) -> WorldModelRevision:
    model["designer_state"] = state_for(model)
    model["semantic_model"] = compile_semantic_model(model)
    latest = await session.scalar(select(func.max(WorldModelRevision.revision)).where(
        WorldModelRevision.project_id == project.id)) or 0
    version.revision_number += 1
    row = WorldModelRevision(organization_id=project.organization_id, project_id=project.id,
        project_version_id=version.id, revision=latest + 1, model_json=model,
        model_hash=canonical_hash(model), source=f"designer_{action.lower()}",
        metadata_json={"version_revision": version.revision_number, "designer_action": action},
        created_by=user.id)
    session.add(row)
    await session.flush()
    await audit(session, project=project, version=version, actor=user.id, action=f"DESIGNER_{action}",
        entity="semantic_model", entity_id=event.get("event_id") if event else row.id,
        metadata={"world_model_revision_id": row.id, "model_hash": row.model_hash,
                  "element_id": event.get("element_id") if event else None,
                  "history_event_id": event.get("event_id") if event else None,
                  "operation": event.get("action") if event else action,
                  "property": event.get("property") if event else None,
                  "reason": event.get("reason") if event else None,
                  "target_event_id": event.get("target_event_id") if event else None,
                  "impacts": event.get("impacts") if event else []})
    if commit:
        await session.commit()
    return row


async def load_editable_model(session: AsyncSession, project_id: str, version_ref: str, user: User):
    project, version = await resolve_project_version(session, project_id, version_ref, user.id, write=True)
    version = await session.scalar(select(ProjectVersion).where(ProjectVersion.id == version.id).with_for_update())
    if version is None:
        raise error(404, "VERSION_NOT_FOUND", "Project version not found")
    if version.status != "DRAFT":
        raise error(409, "VERSION_IMMUTABLE", "Designer edits require a DRAFT version; create a new version to edit committed work",
                    version_status=version.status)
    world = await resolve_world_model(session, version.id)
    model = copy.deepcopy(world.model_json)
    model.setdefault("designer_elements", [])
    model.setdefault("designer_relationships", [])
    model["designer_state"] = state_for(model)
    if not model.get("semantic_model"):
        model["semantic_model"] = compile_semantic_model(model)
    return project, version, world, model, model["designer_state"]


async def check_expected_revision(version: ProjectVersion, expected_revision: int) -> None:
    if version.revision_number != expected_revision:
        raise error(409, "VERSION_CONFLICT", "The project version changed since it was read",
                    expected_revision=expected_revision, current_revision=version.revision_number)

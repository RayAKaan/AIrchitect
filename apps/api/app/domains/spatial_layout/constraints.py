from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from shapely.geometry import Polygon, shape


ENGINE_VERSION = "architectural-constraints-v1.0.0"


class ArchitecturalConstraintError(ValueError):
    def __init__(self, code: str, message: str, context: dict[str, Any] | None = None):
        self.code = code
        self.context = context or {}
        super().__init__(message)


def _hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _verify(payload: dict[str, Any], field: str, code: str) -> str:
    supplied = payload.get(field)
    if not isinstance(supplied, str) or len(supplied) != 64:
        raise ArchitecturalConstraintError(f"{code}_HASH_REQUIRED", f"A valid {field} is required")
    value = dict(payload)
    value.pop(field, None)
    if _hash(value) != supplied:
        raise ArchitecturalConstraintError(f"{code}_HASH_INVALID", f"{field} does not match its payload")
    return supplied


def _constraint(
    code: str,
    classification: str,
    status: str,
    message: str,
    *,
    subject_id: str | None = None,
    actual: Any = None,
    expected: Any = None,
    unit: str | None = None,
) -> dict[str, Any]:
    identity = {
        "code": code,
        "subject_id": subject_id,
        "actual": actual,
        "expected": expected,
        "unit": unit,
    }
    return {
        "constraint_id": _hash(identity),
        "code": code,
        "classification": classification,
        "status": status,
        "subject_id": subject_id,
        "message": message,
        "actual": actual,
        "expected": expected,
        "unit": unit,
    }


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def compile_architectural_constraints(
    layout: dict[str, Any],
    topology: dict[str, Any],
    architectural_elements: dict[str, Any],
    envelope: dict[str, Any],
    *,
    world_model_hash: str,
) -> dict[str, Any]:
    """Evaluate hard building invariants separately from unknowns and preferences."""
    layout_hash = _verify(layout, "layout_hash", "CONSTRAINT_LAYOUT")
    topology_hash = _verify(topology, "topology_hash", "CONSTRAINT_TOPOLOGY")
    elements_hash = _verify(architectural_elements, "elements_hash", "CONSTRAINT_ELEMENTS")
    envelope_hash = envelope.get("envelope_hash")
    if not isinstance(envelope_hash, str) or len(envelope_hash) != 64:
        raise ArchitecturalConstraintError("CONSTRAINT_ENVELOPE_HASH_REQUIRED", "A current envelope hash is required")

    expected_lineage = {
        "world_model_hash": world_model_hash,
        "layout_hash": layout_hash,
        "topology_hash": topology_hash,
    }
    if layout.get("world_model_hash") != world_model_hash or topology.get("world_model_hash") != world_model_hash:
        raise ArchitecturalConstraintError(
            "CONSTRAINT_WORLD_MODEL_MISMATCH",
            "Layout and topology must use the exact current World Model hash",
        )
    if topology.get("layout_hash") != layout_hash:
        raise ArchitecturalConstraintError(
            "CONSTRAINT_TOPOLOGY_LAYOUT_MISMATCH",
            "Topology must be derived from the exact supplied layout",
        )
    element_lineage = architectural_elements.get("source_lineage") or {}
    if (
        element_lineage.get("world_model_hash") != world_model_hash
        or element_lineage.get("layout_hash") != layout_hash
        or element_lineage.get("topology_hash") != topology_hash
    ):
        raise ArchitecturalConstraintError(
            "CONSTRAINT_ELEMENT_LINEAGE_MISMATCH",
            "Architectural elements must use the exact World Model, layout and topology lineage",
        )

    constraints: list[dict[str, Any]] = []
    nodes = {
        item.get("id") for item in topology.get("nodes", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    layout_space_ids = {
        item.get("id") for item in layout.get("spaces", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if nodes != layout_space_ids:
        constraints.append(_constraint(
            "TOPOLOGY_NODE_SET_MATCH",
            "HARD",
            "FAIL",
            "Topology nodes must match the exact layout space set.",
            actual=sorted(nodes),
            expected=sorted(layout_space_ids),
        ))
    else:
        constraints.append(_constraint(
            "TOPOLOGY_NODE_SET_MATCH",
            "HARD",
            "PASS",
            "Topology nodes match the exact layout space set.",
            actual=len(nodes),
            expected=len(layout_space_ids),
            unit="spaces",
        ))

    area = layout.get("area_reconciliation") or {}
    if area.get("reconciled") is True:
        constraints.append(_constraint(
            "PROGRAM_AREA_RECONCILIATION",
            "HARD",
            "PASS",
            "Allocated room area reconciles to selected concept GFA within the layout engine tolerance.",
            actual=area.get("allocated_space_area_m2"),
            expected=area.get("selected_concept_gfa_m2"),
            unit="m2",
        ))
    else:
        constraints.append(_constraint(
            "PROGRAM_AREA_RECONCILIATION",
            "HARD",
            "FAIL",
            "Allocated room area does not reconcile to selected concept GFA.",
            actual=area.get("allocated_space_area_m2"),
            expected=area.get("selected_concept_gfa_m2"),
            unit="m2",
        ))

    footprint = layout.get("footprint") or {}
    footprint_boundary = footprint.get("boundary")
    envelope_polygon = envelope.get("buildable_polygon")
    if isinstance(footprint_boundary, list) and len(footprint_boundary) >= 4 and envelope_polygon:
        try:
            footprint_polygon = Polygon([(float(point[0]), float(point[1])) for point in footprint_boundary])
            buildable = shape(envelope_polygon)
            contained = footprint_polygon.is_valid and buildable.is_valid and buildable.covers(footprint_polygon)
        except (TypeError, ValueError, KeyError):
            contained = False
        constraints.append(_constraint(
            "FOOTPRINT_WITHIN_BUILDABLE_ENVELOPE",
            "HARD",
            "PASS" if contained else "FAIL",
            "The selected footprint must be fully contained by the current buildable envelope.",
            actual=footprint.get("area_m2"),
            expected=envelope.get("max_footprint_m2"),
            unit="m2",
        ))
    else:
        constraints.append(_constraint(
            "FOOTPRINT_WITHIN_BUILDABLE_ENVELOPE",
            "UNKNOWN",
            "UNKNOWN",
            "Buildable polygon evidence is unavailable; footprint containment is not asserted.",
        ))

    max_footprint = envelope.get("max_footprint_m2")
    if _finite(max_footprint) and _finite(footprint.get("area_m2")):
        valid = float(footprint["area_m2"]) <= float(max_footprint) + 0.02
        constraints.append(_constraint(
            "MAXIMUM_FOOTPRINT_AREA",
            "HARD",
            "PASS" if valid else "FAIL",
            "Selected footprint area must not exceed the current envelope maximum.",
            actual=footprint["area_m2"],
            expected=max_footprint,
            unit="m2",
        ))
    else:
        constraints.append(_constraint(
            "MAXIMUM_FOOTPRINT_AREA",
            "UNKNOWN",
            "UNKNOWN",
            "A canonical maximum footprint area is unavailable; no planning limit is assumed.",
            actual=footprint.get("area_m2"),
            expected=max_footprint,
            unit="m2",
        ))

    max_gfa = envelope.get("max_gfa_m2")
    selected_gfa = area.get("selected_concept_gfa_m2")
    if _finite(max_gfa) and _finite(selected_gfa):
        valid = float(selected_gfa) <= float(max_gfa) + 0.02
        constraints.append(_constraint(
            "MAXIMUM_GFA",
            "HARD",
            "PASS" if valid else "FAIL",
            "Selected concept GFA must not exceed the current envelope maximum.",
            actual=selected_gfa,
            expected=max_gfa,
            unit="m2",
        ))
    else:
        constraints.append(_constraint(
            "MAXIMUM_GFA",
            "UNKNOWN",
            "UNKNOWN",
            "A canonical maximum GFA is unavailable; no planning limit is assumed.",
            actual=selected_gfa,
            expected=max_gfa,
            unit="m2",
        ))

    blocking_topology = [
        issue for issue in topology.get("issues", [])
        if isinstance(issue, dict) and issue.get("severity") == "ERROR"
    ]
    constraints.append(_constraint(
        "TOPOLOGY_GEOMETRY_VALID",
        "HARD",
        "FAIL" if blocking_topology else "PASS",
        "Topology must not contain blocking geometry errors.",
        actual=blocking_topology,
        expected=[],
    ))

    for candidate in architectural_elements.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        candidate_id = candidate.get("candidate_id")
        element_type = candidate.get("element_type")
        source_ids = candidate.get("source_space_ids") or []
        source_valid = isinstance(source_ids, list) and all(space_id in nodes for space_id in source_ids)
        constraints.append(_constraint(
            "ELEMENT_SOURCE_SPACE_REFERENCES",
            "HARD",
            "PASS" if source_valid else "FAIL",
            "Every generated element must reference existing topology spaces.",
            subject_id=candidate_id,
            actual=source_ids,
            expected=sorted(set(source_ids) & nodes) if source_valid else sorted(nodes),
        ))
        properties = candidate.get("properties") or {}
        missing = candidate.get("missing_parameters") or []
        if element_type == "Wall":
            start = properties.get("start_m") or {}
            end = properties.get("end_m") or {}
            points_valid = all(_finite(start.get(axis)) and _finite(end.get(axis)) for axis in ("x", "y", "z"))
            length = (
                math.dist(
                    (float(start["x"]), float(start["y"]), float(start["z"])),
                    (float(end["x"]), float(end["y"]), float(end["z"])),
                )
                if points_valid else None
            )
            declared = properties.get("length_m")
            axis_valid = (
                length is not None
                and _finite(declared)
                and abs(length - float(declared)) <= max(1e-4, length * 1e-4)
                and abs(float(start["z"]) - float(end["z"])) <= 1e-5
            )
            constraints.append(_constraint(
                "WALL_AXIS_VALID",
                "HARD",
                "PASS" if axis_valid else "FAIL",
                "Wall axes must be finite, horizontal and consistent with their declared metric length.",
                subject_id=candidate_id,
                actual=length,
                expected=declared,
                unit="m",
            ))
            if missing:
                constraints.append(_constraint(
                    "WALL_DIMENSIONS_COMPLETE",
                    "UNKNOWN",
                    "UNKNOWN",
                    "Wall height/thickness require explicit review; no dimension is inferred.",
                    subject_id=candidate_id,
                    actual=missing,
                    expected=[],
                ))
            else:
                constraints.append(_constraint(
                    "WALL_DIMENSIONS_COMPLETE",
                    "HARD",
                    "PASS",
                    "Wall height and thickness are explicitly supplied.",
                    subject_id=candidate_id,
                ))
        elif element_type == "Slab":
            boundary = properties.get("boundary_m")
            valid = isinstance(boundary, list) and len(boundary) >= 4
            polygon = None
            if valid:
                try:
                    coordinates = [(float(point["x"]), float(point["y"])) for point in boundary]
                    elevations = [float(point["z"]) for point in boundary]
                    polygon = Polygon(coordinates)
                    valid = (
                        coordinates[0] == coordinates[-1]
                        and max(elevations) - min(elevations) <= 1e-6
                        and polygon.is_valid
                        and not polygon.interiors
                        and polygon.area > 1e-6
                    )
                except (TypeError, ValueError, KeyError):
                    valid = False
            declared_area = properties.get("area_m2")
            area_valid = (
                valid and polygon is not None and _finite(declared_area)
                and abs(polygon.area - float(declared_area)) <= max(0.02, polygon.area * 1e-4)
            )
            constraints.append(_constraint(
                "SLAB_BOUNDARY_AND_AREA_VALID",
                "HARD",
                "PASS" if area_valid else "FAIL",
                "Slab boundary must be closed, planar, simple and reconcile to its declared area.",
                subject_id=candidate_id,
                actual=polygon.area if polygon is not None and valid else None,
                expected=declared_area,
                unit="m2",
            ))
            if "thickness_m" in missing:
                constraints.append(_constraint(
                    "SLAB_THICKNESS_COMPLETE",
                    "UNKNOWN",
                    "UNKNOWN",
                    "Slab thickness requires explicit review; no dimension is inferred.",
                    subject_id=candidate_id,
                ))
            else:
                constraints.append(_constraint(
                    "SLAB_THICKNESS_COMPLETE",
                    "HARD",
                    "PASS",
                    "Slab thickness is explicitly supplied.",
                    subject_id=candidate_id,
                ))

    preferred_adjacencies = [
        item for item in layout.get("adjacencies", [])
        if isinstance(item, dict) and not item.get("required")
    ]
    for adjacency in preferred_adjacencies:
        satisfied = adjacency.get("status") == "SATISFIED"
        constraints.append(_constraint(
            "PREFERRED_PROGRAM_ADJACENCY",
            "PREFERRED",
            "PASS" if satisfied else "REVIEW_REQUIRED",
            "Preferred programme adjacency is a design preference, not a hard geometry or code constraint.",
            subject_id=f"{adjacency.get('from')}:{adjacency.get('to')}",
            actual=adjacency.get("status"),
            expected="SATISFIED",
        ))

    required_adjacencies = [
        item for item in layout.get("adjacencies", [])
        if isinstance(item, dict) and item.get("required")
    ]
    for adjacency in required_adjacencies:
        status = adjacency.get("status")
        satisfied = status == "SATISFIED"
        constraints.append(_constraint(
            "REQUIRED_PROGRAM_ADJACENCY",
            "HARD",
            "PASS" if satisfied else "UNKNOWN",
            "Required programme adjacency must be confirmed by spatial topology; adjacency is not proof of traversable access.",
            subject_id=f"{adjacency.get('from')}:{adjacency.get('to')}",
            actual=status,
            expected="SATISFIED",
        ))

    circulation = topology.get("circulation_network") or {}
    constraints.append(_constraint(
        "TRAVERSABLE_CIRCULATION",
        "UNKNOWN",
        "UNKNOWN",
        "Circulation contacts are not traversable routes; doors, access and egress require authoritative review.",
        actual=circulation.get("status"),
        expected="TRAVERSABLE",
    ))
    for unknown in sorted(set(layout.get("unknowns") or []) | set(topology.get("unknowns") or []) | set(architectural_elements.get("unknowns") or [])):
        constraints.append(_constraint(
            "SOURCE_UNKNOWN",
            "UNKNOWN",
            "UNKNOWN",
            f"Source evidence remains unresolved: {unknown}.",
            subject_id=str(unknown),
        ))

    failures = sum(item["classification"] == "HARD" and item["status"] == "FAIL" for item in constraints)
    unknowns = sum(item["status"] == "UNKNOWN" for item in constraints)
    review = sum(item["status"] == "REVIEW_REQUIRED" for item in constraints)
    passed = sum(item["status"] == "PASS" for item in constraints)
    status = "BLOCKED" if failures else "REVIEW_REQUIRED" if unknowns or review else "PASS"
    payload = {
        "schema_version": "phase3-architectural-constraints-v1",
        "engine_version": ENGINE_VERSION,
        "project_id": layout.get("project_id"),
        "project_version_id": layout.get("project_version_id"),
        "status": status,
        "constraints": constraints,
        "summary": {
            "passed": passed,
            "failed": failures,
            "unknown": unknowns,
            "review_required": review,
            "hard_constraints_passed": failures == 0,
        },
        "unknowns": sorted(set(layout.get("unknowns") or []) | set(topology.get("unknowns") or []) | set(architectural_elements.get("unknowns") or [])),
        "source_lineage": {
            **expected_lineage,
            "envelope_hash": envelope_hash,
            "architectural_elements_hash": elements_hash,
        },
    }
    payload["constraints_hash"] = _hash(payload)
    return payload


__all__ = ["ENGINE_VERSION", "ArchitecturalConstraintError", "compile_architectural_constraints"]

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.domains.envelope.schemas import EnvelopeRequest
from app.domains.envelope.service import build_envelope
from app.domains.geometry.engine import generate as generate_geometry
from app.domains.geometry.schemas import GeometryGenerateRequest
from app.domains.structure.engine import generate as generate_structure
from app.domains.structure.schemas import StructuralConceptRequest


@dataclass(frozen=True)
class RegenerationInput:
    artifact_type: str
    source_revision_hash: str
    payload: dict[str, Any]
    dependencies: dict[str, dict[str, Any]] | None = None


@dataclass(frozen=True)
class RegenerationOutput:
    artifact_type: str
    source_revision_hash: str
    payload: dict[str, Any]
    output_hash: str
    engine_version: str


Handler = Callable[[RegenerationInput], RegenerationOutput]


def _content_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _output(request: RegenerationInput, payload: dict[str, Any], engine_version: str) -> RegenerationOutput:
    return RegenerationOutput(
        artifact_type=request.artifact_type,
        source_revision_hash=request.source_revision_hash,
        payload=payload,
        output_hash=_content_hash(payload),
        engine_version=engine_version,
    )


def _geometry_handler(request: RegenerationInput) -> RegenerationOutput:
    raw_request = request.payload.get("regeneration_request")
    if not isinstance(raw_request, dict):
        raise ValueError("geometry artifact is missing regeneration_request")
    geometry_request = GeometryGenerateRequest.model_validate(raw_request)
    artifacts = generate_geometry(geometry_request)
    payload = {
        "project_id": geometry_request.project_id,
        "source_revision": geometry_request.source_revision,
        "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
    }
    return _output(request, payload, "geometry-engine-v1")


def _planning_envelope_handler(request: RegenerationInput) -> RegenerationOutput:
    raw_request = request.payload.get("regeneration_request")
    if not isinstance(raw_request, dict):
        raise ValueError("planning envelope artifact is missing regeneration_request")
    boundary = raw_request.get("boundary_geojson")
    envelope_request = EnvelopeRequest.model_validate(raw_request.get("request", {}))
    if not isinstance(boundary, dict):
        raise ValueError("planning envelope regeneration_request is missing boundary_geojson")
    return _output(request, build_envelope(boundary, envelope_request), "planning-envelope-v1")


def _quantity_handler(request: RegenerationInput) -> RegenerationOutput:
    raw_request = request.payload.get("regeneration_request")
    if not isinstance(raw_request, dict):
        raise ValueError("quantity artifact is missing regeneration_request")
    geometry = raw_request.get("geometry_payload")
    if not isinstance(geometry, dict):
        raise ValueError("quantity regeneration_request is missing geometry_payload")
    required = {"gross_floor_area_m2", "footprint_area_m2", "gross_volume_m3"}
    if not required.issubset(geometry):
        raise ValueError("quantity regeneration_request has incomplete geometry_payload")
    payload = {
        "geometry_artifact_id": raw_request.get("geometry_artifact_id"),
        "geometry_hash": raw_request.get("geometry_hash"),
        "lines": [
            {"code": "gfa", "description": "Gross floor area", "quantity": geometry["gross_floor_area_m2"], "unit": "m2"},
            {"code": "footprint", "description": "Building footprint", "quantity": geometry["footprint_area_m2"], "unit": "m2"},
            {"code": "volume", "description": "Gross massing volume", "quantity": geometry["gross_volume_m3"], "unit": "m3"},
        ],
        "method": "deterministic_rectangular_massing_v1",
    }
    return _output(request, payload, "quantity-engine-v1")


def _cost_handler(request: RegenerationInput) -> RegenerationOutput:
    raw_request = request.payload.get("regeneration_request")
    if not isinstance(raw_request, dict):
        raise ValueError("cost artifact is missing regeneration_request")
    rate = raw_request.get("rate")
    if not isinstance(rate, dict):
        raise ValueError("cost regeneration_request is missing rate")
    try:
        gfa = float(raw_request["gfa_m2"])
        low = float(rate["low"])
        base = float(rate["base"])
        high = float(rate["high"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("cost regeneration_request has invalid numeric inputs") from exc
    payload = {
        "quantity_artifact_id": raw_request.get("quantity_artifact_id"),
        "rate_schedule_id": raw_request.get("rate_schedule_id"),
        "currency": raw_request.get("currency", "SAR"),
        "low": round(gfa * low, 2),
        "base": round(gfa * base, 2),
        "high": round(gfa * high, 2),
        "rate_provenance": raw_request.get("rate_provenance", {}),
        "status": "preliminary",
    }
    return _output(request, payload, "cost-engine-v1")


def _structural_handler(request: RegenerationInput) -> RegenerationOutput:
    raw_request = request.payload.get("regeneration_request")
    if not isinstance(raw_request, dict):
        raise ValueError("structural artifact is missing regeneration_request")
    structural_request = StructuralConceptRequest.model_validate(raw_request)
    result = generate_structure(structural_request)
    return _output(request, result.model_dump(mode="json"), "structural-engine-v1")


def _dependency_payload(request: RegenerationInput, artifact_type: str) -> dict[str, Any]:
    dependency = (request.dependencies or {}).get(artifact_type)
    payload = dependency.get("payload") if isinstance(dependency, dict) else None
    if not isinstance(payload, dict):
        raise ValueError(f"regeneration dependency is missing or not current: {artifact_type}")
    return payload


def _spatial_layout_handler(request: RegenerationInput) -> RegenerationOutput:
    from app.domains.spatial_layout.service import build_spatial_layout

    raw = request.payload.get("regeneration_request")
    if not isinstance(raw, dict):
        raise ValueError("spatial layout artifact is missing regeneration_request")
    payload = build_spatial_layout(
        project_id=raw["project_id"],
        project_version_id=raw["project_version_id"],
        world_model_hash=request.source_revision_hash,
        program=raw["program"],
        envelope=raw["envelope"],
        alternative_id=raw["alternative_id"],
        design_parameters=raw["design_parameters"],
        design_metrics=raw["design_metrics"],
    )
    return _output(request, payload, "phase3-spatial-layout-v1")


def _spatial_topology_handler(request: RegenerationInput) -> RegenerationOutput:
    from app.domains.spatial_layout.topology import build_spatial_topology

    layout = _dependency_payload(request, "spatial_layout")
    return _output(request, build_spatial_topology(layout), "phase3-spatial-topology-v1")


def _architectural_elements_handler(request: RegenerationInput) -> RegenerationOutput:
    from app.domains.spatial_layout.architectural_elements import compile_architectural_elements

    layout = _dependency_payload(request, "spatial_layout")
    topology = _dependency_payload(request, "spatial_topology")
    raw = request.payload.get("regeneration_request") or {}
    if not isinstance(raw, dict):
        raise ValueError("architectural elements regeneration_request must be an object")
    payload = compile_architectural_elements(
        layout,
        topology,
        default_wall_thickness_m=raw.get("default_wall_thickness_m"),
    )
    return _output(request, payload, "phase3-architectural-elements-v1")


def _architectural_constraints_handler(request: RegenerationInput) -> RegenerationOutput:
    from app.domains.spatial_layout.constraints import compile_architectural_constraints

    layout = _dependency_payload(request, "spatial_layout")
    topology = _dependency_payload(request, "spatial_topology")
    elements = _dependency_payload(request, "architectural_elements")
    envelope = _dependency_payload(request, "planning_envelope")
    payload = compile_architectural_constraints(
        layout,
        topology,
        elements,
        envelope,
        world_model_hash=request.source_revision_hash,
    )
    return _output(request, payload, "phase3-architectural-constraints-v1")


class RegenerationHandlerRegistry:
    """Explicit registry; unsupported or evidence-dependent types fail closed."""

    def __init__(self, handlers: dict[str, Handler] | None = None) -> None:
        defaults = {
            "geometry": _geometry_handler,
            "planning_envelope": _planning_envelope_handler,
            "quantity": _quantity_handler,
            "cost": _cost_handler,
            "structural": _structural_handler,
            "spatial_layout": _spatial_layout_handler,
            "spatial_topology": _spatial_topology_handler,
            "architectural_elements": _architectural_elements_handler,
            "architectural_constraints": _architectural_constraints_handler,
        }
        self._handlers = {**defaults, **(handlers or {})}

    def supports(self, artifact_type: str) -> bool:
        """Whether this registry can regenerate an artifact type deterministically."""
        return artifact_type in self._handlers

    def execute(self, request: RegenerationInput) -> RegenerationOutput:
        handler = self._handlers.get(request.artifact_type)
        if handler is None:
            raise ValueError(f"no regeneration handler registered for {request.artifact_type}")
        output = handler(request)
        if output.artifact_type != request.artifact_type:
            raise ValueError("regeneration handler changed artifact identity")
        if output.source_revision_hash != request.source_revision_hash:
            raise ValueError("regeneration handler changed source revision identity")
        if output.output_hash != _content_hash(output.payload):
            raise ValueError("regeneration handler returned an invalid output hash")
        return output

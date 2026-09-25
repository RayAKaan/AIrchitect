from __future__ import annotations
import hashlib
import json
import math
from .schemas import StructuralConceptRequest, StructuralConceptResponse


def _axis(length: float, max_bay: float) -> list[float]:
    bays = max(1, math.ceil(length / max_bay))
    return [round(length * i / bays, 4) for i in range(bays + 1)]


def generate(request: StructuralConceptRequest) -> StructuralConceptResponse:
    x = _axis(request.footprint_width_m, request.preferred_max_bay_m)
    y = _axis(request.footprint_depth_m, request.preferred_max_bay_m)
    columns_per_level = len(x) * len(y)
    beams_per_floor = (len(x) - 1) * len(y) + (len(y) - 1) * len(x)
    payload = request.model_dump(mode='json')
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    missing_load = request.imposed_load_kpa is None
    return StructuralConceptResponse(
        concept_id=f'struct-{digest[:20]}', project_id=request.project_id,
        geometry_artifact_id=request.geometry_artifact_id, geometry_sha256=request.geometry_sha256,
        source_revision=request.source_revision, system=request.system,
        grid={'x_axes_m': x, 'y_axes_m': y, 'columns_per_level': columns_per_level,
              'nominal_max_bay_m': max(max(b-a for a,b in zip(x,x[1:])), max(b-a for a,b in zip(y,y[1:])))},
        preliminary_quantities={'column_positions': columns_per_level,
            'conceptual_beam_segments_per_floor': beams_per_floor,
            'floor_count': request.floors, 'building_height_m': round(request.floors * request.floor_to_floor_m, 3),
            'load_basis': 'not_provided' if missing_load else f'user_supplied:{request.imposed_load_kpa} kPa'},
        input_completeness={'imposed_load_provided': not missing_load,
            'soil_report_available': request.soil_report_available,
            'geometry_hash_bound': bool(request.geometry_sha256)},
        checks={'grid_coordinates_positive_and_ordered': all(v >= 0 for v in x+y) and x == sorted(set(x)) and y == sorted(set(y)),
            'bay_spacing_within_preference': max(max(b-a for a,b in zip(x,x[1:])), max(b-a for a,b in zip(y,y[1:]))) <= request.preferred_max_bay_m + 1e-4,
            'structural_capacity_checked': False, 'code_compliance_checked': False,
            'foundation_design_checked': False},
        limitations=[
            'Conceptual grid only; not a structural design or engineering calculation.',
            'No member sizing, reinforcement, stability, seismic/wind analysis, foundation design, or code verification.',
            'Grid counts are indicative and must be reviewed by a licensed structural engineer.',
            'Geometry hash is carried as provenance; the API does not independently retrieve or verify the artifact.',
        ], status='concept_only')

from __future__ import annotations
import hashlib
import json
from .schemas import GeometryArtifact, GeometryGenerateRequest


def generate(request: GeometryGenerateRequest) -> list[GeometryArtifact]:
    artifacts = []
    for option in sorted(request.options, key=lambda item: item.option_id):
        width = request.footprint_width_m - 2 * option.setback_m
        depth = request.footprint_depth_m - 2 * option.setback_m
        area = width * depth
        height = option.floors * option.floor_to_floor_m
        # One deterministic closed cuboid mesh per massing option.
        vertices = [
            (0.0, 0.0, 0.0), (width, 0.0, 0.0), (width, depth, 0.0), (0.0, depth, 0.0),
            (0.0, 0.0, height), (width, 0.0, height), (width, depth, height), (0.0, depth, height),
        ]
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        canonical = json.dumps({'vertices': vertices, 'faces': faces}, separators=(',', ':'), sort_keys=True)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        artifacts.append(GeometryArtifact(
            artifact_id=f'geom-{digest[:16]}', option_id=option.option_id,
            source_revision=request.source_revision, vertices=vertices, faces=faces,
            footprint_area_m2=round(area, 6), gross_floor_area_m2=round(area * option.floors, 6),
            gross_volume_m3=round(area * height, 6), height_m=round(height, 6),
            geometry_sha256=digest,
            validation={'positive_dimensions': width > 0 and depth > 0 and height > 0,
                        'closed_cuboid_mesh': True, 'regulatory_compliance': 'not_evaluated',
                        'engineering_approval': 'not_evaluated'},
        ))
    return artifacts

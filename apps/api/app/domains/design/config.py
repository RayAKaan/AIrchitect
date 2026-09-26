from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DesignEngineConfig:
    engine_version: str = "0.2.0"
    config_version: str = "phase2-mvp-1"
    geometry_engine_name: str = "MassingGeometryEngine"
    geometry_engine_version: str = "0.2.0"
    default_floor_height_m: float = 4.0
    minimum_floor_height_m: float = 3.2
    maximum_floor_height_m: float = 5.5
    default_floor_count: int = 4
    minimum_floor_count: int = 1
    maximum_floor_count: int = 20
    default_core_ratio: float = 0.12
    minimum_floor_plate_m2: float = 120.0
    default_max_coverage: float = 0.70
    default_target_coverage: float = 0.55
    gfa_tolerance_ratio: float = 0.05
    coverage_tolerance: float = 1e-6
    default_site_aspect_ratio: float = 1.0
    default_setback_m: float = 0.0
    preliminary_grid_spacing_m: float = 8.0
    max_scene_objects: int = 1000
    max_coordinate_m: float = 10000.0

    def canonical(self) -> dict[str, str | float | int]:
        return asdict(self)


DEFAULT_CONFIG = DesignEngineConfig()

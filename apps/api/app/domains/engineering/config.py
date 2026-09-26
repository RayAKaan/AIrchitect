from dataclasses import asdict,dataclass

@dataclass(frozen=True)
class EngineeringConfig:
    config_version:str="phase3-mvp-1"
    quantity_engine_name:str="GeometryQuantityEngine"
    quantity_engine_version:str="0.3.0"
    cost_engine_name:str="ConceptualCostEngine"
    cost_engine_version:str="0.3.0"
    structural_engine_name:str="StructuralConceptEngine"
    structural_engine_version:str="0.3.0"
    regulatory_engine_name:str="RulesetRegulatoryEngine"
    regulatory_engine_version:str="0.3.0"
    validation_engine_name:str="EngineeringValidationEngine"
    validation_engine_version:str="0.3.0"
    external_wall_uncertainty_ratio:float=.05
    quantity_tolerance:float=1e-4
    high_building_height_m:float=40.0
    long_span_m:float=9.0
    high_aspect_ratio:float=3.0
    def canonical(self):return asdict(self)
DEFAULT_CONFIG=EngineeringConfig()

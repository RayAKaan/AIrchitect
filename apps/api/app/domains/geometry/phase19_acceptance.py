from __future__ import annotations

from dataclasses import dataclass

from .authority import GeometryAuthorityInput, require_authoritative_geometry
from .staleness import GeometryStaleness, require_current_geometry
from app.domains.cad.validation_contract import CadValidationContract, require_validated_cad_run
from app.domains.engineering.cost_contract import CostInputContract, require_cost_inputs
from app.domains.engineering.quantity_contract import QuantityInputContract, require_quantity_inputs
from app.domains.engineering.regulatory_contract import RegulatoryInputContract, require_regulatory_inputs
from app.domains.engineering.structural_contract import StructuralInputContract, require_structural_inputs


@dataclass(frozen=True)
class Phase19Acceptance:
    accepted: bool
    reasons: tuple[str, ...]


def evaluate_phase19_acceptance(
    *,
    geometry: GeometryAuthorityInput,
    staleness: GeometryStaleness,
    cad_validation: CadValidationContract,
    quantity: QuantityInputContract,
    structural: StructuralInputContract,
    regulatory: RegulatoryInputContract,
    cost: CostInputContract,
) -> Phase19Acceptance:
    checks = (
        (require_authoritative_geometry, geometry),
        (require_current_geometry, staleness),
        (require_validated_cad_run, cad_validation),
        (require_quantity_inputs, quantity),
        (require_structural_inputs, structural),
        (require_regulatory_inputs, regulatory),
        (require_cost_inputs, cost),
    )
    reasons: list[str] = []
    for check, value in checks:
        try:
            check(value)
        except ValueError as exc:
            reasons.append(str(exc))
    return Phase19Acceptance(accepted=not reasons, reasons=tuple(reasons))

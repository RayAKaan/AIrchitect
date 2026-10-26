from app.domains.cad.validation_contract import CadValidationContract
from app.domains.engineering.cost_contract import CostInputContract
from app.domains.engineering.quantity_contract import QuantityInputContract
from app.domains.engineering.regulatory_contract import RegulatoryInputContract
from app.domains.engineering.structural_contract import StructuralInputContract
from app.domains.geometry.authority import GeometryAuthorityInput, GeometrySource
from app.domains.geometry.phase19_acceptance import evaluate_phase19_acceptance
from app.domains.geometry.staleness import GeometryStaleness


def _inputs():
    return {
        "geometry": GeometryAuthorityInput(GeometrySource.CAD_BREP, True, True, True, True, True),
        "staleness": GeometryStaleness("g", "world", "world", "design", "design"),
        "cad_validation": CadValidationContract("SUCCEEDED", {"valid": True, "checks": [{"status": "PASS"}], "errors": []}),
        "quantity": QuantityInputContract("geometry", "g", "world", "design"),
        "structural": StructuralInputContract("g", "q", "world", "design"),
        "regulatory": RegulatoryInputContract("g", "q", "world", "design", "rules"),
        "cost": CostInputContract("q", "rates", "SAR"),
    }


def test_phase19_acceptance_requires_the_full_canonical_chain() -> None:
    result = evaluate_phase19_acceptance(**_inputs())
    assert result.accepted
    assert result.reasons == ()


def test_phase19_acceptance_collects_fail_closed_reasons() -> None:
    values = _inputs()
    values["geometry"] = GeometryAuthorityInput(GeometrySource.LEGACY_IR, True, True, True, True, True)
    values["staleness"] = GeometryStaleness("g", "new-world", "world", "design", "design")

    result = evaluate_phase19_acceptance(**values)

    assert not result.accepted
    assert "CAD_REQUIRED" in result.reasons
    assert "GEOMETRY_STALE: WORLD_MODEL_CHANGED" in result.reasons

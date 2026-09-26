import pytest
from pydantic import ValidationError

from app.domains.lifecycle.service import canonical_hash
from app.domains.requirements.extractor import DeterministicRequirementExtractor
from app.domains.world_model.model import Building, BuildingWorldModel, Quantity, Site


def test_normalization_and_extractor_provider_are_deterministic():
    brief = "Six-floor retail in Riyadh with 18,000 square meters GFA on a 3,000 sqm site and basement parking."
    extractor = DeterministicRequirementExtractor()
    first, second = extractor.extract(brief), extractor.extract(brief)
    assert first == second
    values = {item.parameter: (item.normalized_value, item.unit) for item in first}
    assert values["floor_count"] == (6, "count")
    assert values["target_gfa"] == (18000.0, "m2")
    assert values["site_area"] == (3000.0, "m2")


def test_world_model_hash_ignores_dictionary_order():
    a = {"building": {"floor_count": 6, "use": "retail"}, "site": {"area": 3000}}
    b = {"site": {"area": 3000}, "building": {"use": "retail", "floor_count": 6}}
    assert canonical_hash(a) == canonical_hash(b)


def test_unknown_is_not_zero():
    model = BuildingWorldModel(project_id="p", project_version_id="v")
    assert model.site.area is None
    assert model.building.floor_count is None


def test_invalid_positive_quantities_are_rejected():
    with pytest.raises(ValidationError):
        BuildingWorldModel(project_id="p", project_version_id="v",
            site=Site(area=Quantity(value=0, unit="m2")), building=Building(floor_count=1))

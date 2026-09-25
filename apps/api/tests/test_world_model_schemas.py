import pytest
from pydantic import ValidationError
from app.domains.world_model.schemas import BuildingModel, BuildingLevel, BuildingSpace, Dimension

def test_empty_world_model_is_valid():
    assert BuildingModel().schema_version == '1.0.0'

def test_space_must_reference_existing_level():
    with pytest.raises(ValidationError, match='unknown levels'):
        BuildingModel(spaces=[BuildingSpace(space_id='s1', name='Retail', level_id='L1', area=Dimension(value=100))])

def test_level_ids_must_be_unique():
    level = BuildingLevel(level_id='L1', name='Ground')
    with pytest.raises(ValidationError, match='unique'):
        BuildingModel(levels=[level, level])

def test_dimensions_must_be_positive():
    with pytest.raises(ValidationError):
        Dimension(value=0)

def test_provenance_confidence_is_bounded():
    with pytest.raises(ValidationError):
        BuildingModel(provenance={'site': {'confidence': 1.5}})

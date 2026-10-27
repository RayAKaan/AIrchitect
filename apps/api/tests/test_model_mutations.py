import pytest

from app.domains.model.commands import ModelCommand
from app.domains.model.mutations import ModelMutationError, apply_commands
from app.domains.model.schemas import ArchitecturalModel, Building, Site


def base_model() -> ArchitecturalModel:
    site = Site(id="site", width_m=20, depth_m=20)
    return ArchitecturalModel(
        project_id="project", revision=4, site=site,
        buildings=(Building(id="building", name="Building", site_id=site.id),),
    )


def test_batch_applies_atomically_and_increments_revision_once() -> None:
    model = base_model()
    create = ModelCommand(
        command_id="level-create", operation="create", element_type="level", element_id="level-1", expected_revision=4,
        payload={"building_id": "building", "name": "Ground", "elevation_m": 0, "height_m": 3},
    )
    update = ModelCommand(
        command_id="level-update", operation="update", element_type="level", element_id="level-1", expected_revision=4,
        payload={"name": "Ground Floor"},
    )
    result = apply_commands(model, (create, update))
    assert result.revision == 5
    assert result.levels[0].name == "Ground Floor"
    assert model.levels == ()


def test_invalid_later_command_does_not_change_original_model() -> None:
    model = base_model()
    create = ModelCommand(
        command_id="level-create", operation="create", element_type="level", element_id="level-1", expected_revision=4,
        payload={"building_id": "building", "name": "Ground", "elevation_m": 0, "height_m": 3},
    )
    delete = ModelCommand(
        command_id="missing-delete", operation="delete", element_type="level", element_id="missing", expected_revision=4,
    )
    with pytest.raises(ModelMutationError, match="does not exist"):
        apply_commands(model, (create, delete))
    assert model.levels == ()


def test_stale_revision_is_rejected() -> None:
    command = ModelCommand(
        command_id="level-create", operation="create", element_type="level", element_id="level-1", expected_revision=3,
        payload={"building_id": "building", "name": "Ground", "elevation_m": 0, "height_m": 3},
    )
    with pytest.raises(ModelMutationError, match="targets revision 3"):
        apply_commands(base_model(), (command,))

import pytest

from app.domains.model import ArchitecturalModel, Building, Level, Point3D, Site, Space
from app.domains.model.regulatory import RegulatoryRuleSet, screen_model


def _model() -> ArchitecturalModel:
    return ArchitecturalModel(
        project_id="p",
        revision=1,
        site=Site(id="s", width_m=20, depth_m=20),
        buildings=(Building(id="b", name="Main", site_id="s"),),
        levels=(Level(id="l", building_id="b", name="Ground", elevation_m=0, height_m=3),),
        spaces=(Space(id="room", level_id="l", name="Room", boundary=(
            Point3D(x=2, y=2, z=0), Point3D(x=6, y=2, z=0),
            Point3D(x=6, y=5, z=0), Point3D(x=2, y=5, z=0),
        )),),
    )


def test_regulatory_screen_passes_within_envelope() -> None:
    result = screen_model(_model(), RegulatoryRuleSet(front_setback_m=1, rear_setback_m=1, side_setback_m=1))
    assert result.passed is True
    assert result.findings[0].status == "PASS"
    assert result.jurisdiction_specific_required is True


def test_regulatory_screen_rejects_setback_violation() -> None:
    result = screen_model(_model(), RegulatoryRuleSet(front_setback_m=3))
    assert result.passed is False
    assert result.findings[0].code == "SETBACK_ENVELOPE"


def test_negative_setback_is_invalid() -> None:
    with pytest.raises(ValueError, match="setbacks"):
        screen_model(_model(), RegulatoryRuleSet(front_setback_m=-1))

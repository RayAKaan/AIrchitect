import pytest

from app.domains.commands.regeneration_executor import RegenerationHandlerRegistry, RegenerationInput


def test_geometry_regeneration_is_deterministic() -> None:
    request = RegenerationInput(
        artifact_type="geometry",
        source_revision_hash="revision-hash",
        payload={
            "regeneration_request": {
                "project_id": "project",
                "source_revision": 2,
                "footprint_width_m": 20,
                "footprint_depth_m": 30,
                "options": [
                    {"option_id": "main", "floors": 3, "floor_to_floor_m": 3.6, "setback_m": 2},
                ],
            }
        },
    )
    registry = RegenerationHandlerRegistry()
    first = registry.execute(request)
    second = registry.execute(request)
    assert first.output_hash == second.output_hash
    assert first.payload == second.payload
    assert first.source_revision_hash == "revision-hash"


def test_unknown_artifact_type_fails_closed() -> None:
    with pytest.raises(ValueError, match="no regeneration handler"):
        RegenerationHandlerRegistry().execute(
            RegenerationInput("unknown", "revision", {})
        )


def test_geometry_requires_explicit_replay_input() -> None:
    with pytest.raises(ValueError, match="regeneration_request"):
        RegenerationHandlerRegistry().execute(
            RegenerationInput("geometry", "revision", {})
        )

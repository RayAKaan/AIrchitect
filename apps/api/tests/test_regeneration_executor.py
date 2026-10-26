import pytest

from app.domains.commands.regeneration_executor import RegenerationHandlerRegistry, RegenerationInput, RegenerationOutput


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


def test_registry_verifies_handler_identity_and_hash() -> None:
    def handler(request: RegenerationInput) -> RegenerationOutput:
        return RegenerationOutput(
            artifact_type=request.artifact_type,
            source_revision_hash=request.source_revision_hash,
            payload={"value": 1},
            output_hash="wrong",
            engine_version="test-v1",
        )

    registry = RegenerationHandlerRegistry({"test": handler})
    with pytest.raises(ValueError, match="invalid output hash"):
        registry.execute(RegenerationInput("test", "b" * 64, {}))


def test_quantity_handler_is_deterministic() -> None:
    request = RegenerationInput(
        artifact_type="quantity",
        source_revision_hash="c" * 64,
        payload={
            "regeneration_request": {
                "geometry_artifact_id": "geometry-1",
                "geometry_hash": "d" * 64,
                "geometry_payload": {
                    "gross_floor_area_m2": 100.0,
                    "footprint_area_m2": 50.0,
                    "gross_volume_m3": 400.0,
                },
            }
        },
    )
    registry = RegenerationHandlerRegistry()
    first = registry.execute(request)
    second = registry.execute(request)
    assert first.payload == second.payload
    assert first.output_hash == second.output_hash
    assert first.engine_version == "quantity-engine-v1"

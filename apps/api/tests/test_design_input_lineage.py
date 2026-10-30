from types import SimpleNamespace

from app.domains.design.engine import ENGINE


def test_generation_key_changes_when_program_or_envelope_changes():
    original = ENGINE.generation_key("world-hash", {"program": "program-v1", "envelope": "envelope-v1"})

    assert original == ENGINE.generation_key(
        "world-hash", {"envelope": "envelope-v1", "program": "program-v1"}
    )
    assert original != ENGINE.generation_key(
        "world-hash", {"program": "program-v2", "envelope": "envelope-v1"}
    )
    assert original != ENGINE.generation_key(
        "world-hash", {"program": "program-v1", "envelope": "envelope-v2"}
    )


def test_design_hash_changes_when_input_artifact_lineage_changes():
    candidate = SimpleNamespace(
        strategy_id="balanced",
        strategy_version="1.0",
        parameters={"floor_count": 4, "footprint_width_m": 30.0},
    )
    original = ENGINE._design_hash(
        "world-hash", candidate, {"program": "program-v1", "envelope": "envelope-v1"}
    )

    assert original != ENGINE._design_hash(
        "world-hash", candidate, {"program": "program-v2", "envelope": "envelope-v1"}
    )
    assert original != ENGINE._design_hash(
        "world-hash", candidate, {"program": "program-v1", "envelope": "envelope-v2"}
    )

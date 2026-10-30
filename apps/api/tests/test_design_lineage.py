from types import SimpleNamespace

from app.domains.design.lineage import alternative_is_stale


def alternative(world_hash="world-1", provenance=None):
    return SimpleNamespace(
        input_world_model_hash=world_hash,
        provenance_json=provenance or {},
    )


def test_world_model_mismatch_marks_alternative_stale():
    assert alternative_is_stale(alternative("world-old"), "world-current", {})


def test_legacy_world_only_alternative_remains_current_without_program_or_envelope():
    assert not alternative_is_stale(alternative(), "world-1", {"program": None, "envelope": None})


def test_legacy_alternative_is_stale_once_current_program_and_envelope_exist():
    assert alternative_is_stale(
        alternative(),
        "world-1",
        {"program": "program-hash", "envelope": "envelope-hash"},
    )


def test_program_hash_mismatch_marks_alternative_stale():
    row = alternative(provenance={"input_lineage": {"program": "old-program", "envelope": "envelope-1"}})
    assert alternative_is_stale(row, "world-1", {"program": "new-program", "envelope": "envelope-1"})


def test_envelope_hash_mismatch_marks_alternative_stale():
    row = alternative(provenance={"input_lineage": {"program": "program-1", "envelope": "old-envelope"}})
    assert alternative_is_stale(row, "world-1", {"program": "program-1", "envelope": "new-envelope"})


def test_matching_world_program_and_envelope_lineage_remains_current():
    row = alternative(provenance={"input_lineage": {"program": "program-1", "envelope": "envelope-1"}})
    assert not alternative_is_stale(row, "world-1", {"program": "program-1", "envelope": "envelope-1"})

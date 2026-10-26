from app.domains.commands.contract import canonical_payload, validate_payload_contract


def test_translation_vectors_are_canonicalized():
    from app.domains.commands.schemas import CommandEnvelope

    command = CommandEnvelope(
        command_id="c1", type="MoveBuilding", schema_version=1,
        project_id="p", version_id="v", base_revision_hash="h",
        idempotency_key="idem-12345678", payload={"element_id": "b", "translation_m": {"x": 1, "y": 2}},
        reason="move building",
    )
    assert canonical_payload(command)["translation_m"] == {"x": 1.0, "y": 2.0, "z": 0.0}


def test_invalid_numeric_payload_fails_closed():
    from app.domains.commands.schemas import CommandEnvelope

    command = CommandEnvelope(
        command_id="c2", type="ResizeSpace", schema_version=1,
        project_id="p", version_id="v", base_revision_hash="h",
        idempotency_key="idem-12345679", payload={"element_id": "s", "area_m2": "large"},
        reason="resize space",
    )
    result = validate_payload_contract(command)
    assert not result.valid
    assert result.errors

import pytest

from app.domains.lifecycle.pipeline_stage import StageInput, StageOutput, validate_stage_output


def test_stage_input_hash_is_canonical() -> None:
    first = StageInput.create(
        stage="geometry",
        workflow_id="w1",
        project_version_id="v1",
        source_revision_hash="source",
        payload={"b": 2, "a": 1},
    )
    second = StageInput.create(
        stage="geometry",
        workflow_id="w1",
        project_version_id="v1",
        source_revision_hash="source",
        payload={"a": 1, "b": 2},
    )
    assert first.input_hash == second.input_hash


def test_stage_output_cannot_change_revision() -> None:
    stage_input = StageInput.create(
        stage="geometry",
        workflow_id="w1",
        project_version_id="v1",
        source_revision_hash="source",
        payload={},
    )
    output = StageOutput.create(
        stage="geometry",
        source_revision_hash="other",
        payload={},
        engine_version="1",
    )
    with pytest.raises(ValueError, match="source revision"):
        validate_stage_output(stage_input, output)

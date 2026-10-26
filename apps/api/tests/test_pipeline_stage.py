from __future__ import annotations

import pytest

from app.domains.lifecycle.pipeline_stage import PipelineStageRegistry, StageInput, StageOutput


@pytest.mark.asyncio
async def test_stage_registry_preserves_canonical_hash_identity():
    async def handler(session, stage_input):
        return StageOutput.create(
            stage=stage_input.stage,
            source_revision_hash=stage_input.source_revision_hash,
            payload={"value": 2},
            engine_version="test-v1",
        )

    registry = PipelineStageRegistry({"geometry": handler})
    stage_input = StageInput.create(
        stage="geometry",
        workflow_id="workflow",
        project_version_id="version",
        source_revision_hash="a" * 64,
        payload={"value": 1},
    )
    output = await registry.execute(None, stage_input)
    assert output.output_hash
    assert output.source_revision_hash == stage_input.source_revision_hash


@pytest.mark.asyncio
async def test_stage_registry_rejects_hash_mismatch():
    async def handler(session, stage_input):
        return StageOutput(
            stage=stage_input.stage,
            source_revision_hash=stage_input.source_revision_hash,
            payload={"value": 2},
            output_hash="wrong",
            engine_version="test-v1",
        )

    with pytest.raises(ValueError, match="invalid output hash"):
        await PipelineStageRegistry({"geometry": handler}).execute(
            None,
            StageInput.create(
                stage="geometry",
                workflow_id="workflow",
                project_version_id="version",
                source_revision_hash="a" * 64,
                payload={},
            ),
        )


def test_stage_registry_fails_closed_for_unknown_stage():
    with pytest.raises(ValueError, match="no pipeline stage handler"):
        PipelineStageRegistry().get("unknown")

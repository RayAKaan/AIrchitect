import pytest
from pydantic import ValidationError
from app.domains.change_impact.schemas import ChangeImpactRequest
from app.domains.change_impact.engine import analyze


def request():
    return ChangeImpactRequest(project_id="p1", changed_artifact_ids=["site"], new_source_revision="r2", artifacts=[
        {"artifact_id":"site","artifact_type":"site_input","revision":"r2"},
        {"artifact_id":"geometry","artifact_type":"geometry","revision":"g1","depends_on":["site"]},
        {"artifact_id":"estimate","artifact_type":"estimate","revision":"e1","depends_on":["geometry"]},
        {"artifact_id":"unrelated","artifact_type":"note","revision":"n1"},
    ])


def test_transitive_dependants_become_stale():
    result = analyze(request())
    assert [x.artifact_id for x in result.impacted] == ["geometry", "estimate"]
    assert all(x.resulting_status == "stale" for x in result.impacted)
    assert result.impacted[1].dependency_path == ["site", "geometry", "estimate"]
    assert result.unchanged_artifact_ids == ["unrelated"]


def test_direct_change_is_not_reported_as_its_own_downstream_impact():
    result = analyze(request())
    assert "site" not in [x.artifact_id for x in result.impacted]


def test_rejects_unknown_dependency():
    body = request().model_dump()
    body["artifacts"][1]["depends_on"] = ["missing"]
    with pytest.raises(ValidationError):
        ChangeImpactRequest(**body)


def test_rejects_duplicate_ids():
    body = request().model_dump()
    body["artifacts"].append(body["artifacts"][0])
    with pytest.raises(ValidationError):
        ChangeImpactRequest(**body)


def test_cycles_terminate_and_mark_reachable_nodes():
    body = ChangeImpactRequest(project_id="p", changed_artifact_ids=["a"], new_source_revision="2", artifacts=[
        {"artifact_id":"a","artifact_type":"input","revision":"1","depends_on":["b"]},
        {"artifact_id":"b","artifact_type":"derived","revision":"1","depends_on":["a"]},
    ])
    assert [x.artifact_id for x in analyze(body).impacted] == ["b"]

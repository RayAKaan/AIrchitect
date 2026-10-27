from app.domains.ai.context import build_copilot_context


def test_context_is_deterministic_and_evidence_is_stably_ordered() -> None:
    first = build_copilot_context(
        project_id="p",
        version_id="v",
        revision_hash="r",
        world_model={"spaces": ["A"]},
        evidence=(
            {"id": "2", "type": "site", "label": "B", "payload": {}},
            {"id": "1", "type": "site", "label": "A", "payload": {}},
        ),
    )
    second = build_copilot_context(
        project_id="p",
        version_id="v",
        revision_hash="r",
        world_model={"spaces": ["A"]},
        evidence=(
            {"id": "1", "type": "site", "label": "A", "payload": {}},
            {"id": "2", "type": "site", "label": "B", "payload": {}},
        ),
    )

    assert first.context_hash == second.context_hash
    assert [item["id"] for item in first.payload["evidence"]] == ["1", "2"]
    assert first.payload["content_is_untrusted_data"] is True


def test_context_limits_evidence() -> None:
    context = build_copilot_context(
        project_id="p",
        version_id="v",
        revision_hash="r",
        world_model={},
        evidence=({"id": "1"}, {"id": "2"}),
        max_evidence=1,
    )

    assert len(context.payload["evidence"]) == 1


def test_context_requires_identity() -> None:
    try:
        build_copilot_context(project_id="", version_id="v", revision_hash="r", world_model={})
    except ValueError as exc:
        assert "identity" in str(exc)
    else:
        raise AssertionError("expected identity validation")

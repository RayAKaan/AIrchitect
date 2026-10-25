from app.domains.commands.regeneration_state import RegenerationState, invalidate


def test_regeneration_state_follows_current_to_current_lifecycle() -> None:
    state = RegenerationState("artifact", "rev-1", "CURRENT", "rev-1")
    invalidated = invalidate(state, "rev-2")
    assert invalidated.status == "INVALIDATED"
    stale = invalidated.transition("STALE")
    queued = stale.transition("QUEUED")
    running = queued.transition("RUNNING")
    succeeded = running.transition("SUCCEEDED")
    current = succeeded.transition("CURRENT", output_revision_hash="rev-2")
    assert current.status == "CURRENT"
    assert current.output_revision_hash == "rev-2"


def test_regeneration_state_rejects_invalid_transition() -> None:
    state = RegenerationState("artifact", "rev-1", "CURRENT", "rev-1")
    try:
        state.transition("RUNNING")
    except ValueError as exc:
        assert "invalid regeneration transition" in str(exc)
    else:
        raise AssertionError("expected transition rejection")


def test_regeneration_state_rejects_active_retargeting() -> None:
    state = RegenerationState("artifact", "rev-1", "RUNNING")
    try:
        invalidate(state, "rev-2")
    except ValueError as exc:
        assert "active regeneration" in str(exc)
    else:
        raise AssertionError("expected active-task rejection")


def test_current_requires_matching_output_revision() -> None:
    state = RegenerationState("artifact", "rev-2", "SUCCEEDED")
    try:
        state.transition("CURRENT", output_revision_hash="rev-1")
    except ValueError as exc:
        assert "source revision" in str(exc)
    else:
        raise AssertionError("expected output revision rejection")

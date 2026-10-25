from app.domains.commands.history_query import project_history


def test_history_projection_is_stable_and_paginated():
    state = {"history": [
        {"command_id": "a", "command_type": "MoveBuilding", "fingerprint": "fa", "status": "committed", "result": {"secret": "x"}},
        {"command_id": "b", "command_type": "Undo", "fingerprint": "fb", "status": "committed"},
    ]}
    assert project_history(state, limit=1)[0].sequence == 1
    assert project_history(state, after=1)[0].command_id == "b"
    assert not hasattr(project_history(state)[0], "result")

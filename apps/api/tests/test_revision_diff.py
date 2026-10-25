from app.domains.commands.revision_diff import diff_semantic_models


def test_diff_classifies_added_removed_and_changed_elements() -> None:
    before = {"semantic_model": {"elements": [{"id": "a", "x": 1}, {"id": "gone", "x": 0}]}}
    after = {"semantic_model": {"elements": [{"id": "a", "x": 2}, {"id": "new", "x": 3}]}}
    diff = diff_semantic_models(before, after)
    assert diff.added == ("new",)
    assert diff.removed == ("gone",)
    assert diff.changed == ("a",)

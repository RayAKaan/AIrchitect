import pytest

from app.domains.change_impact.persistence import dependency_paths


def test_dependency_paths_are_transitive_and_exclude_changed_sources_by_default():
    ids = ["site", "design", "geometry", "quantities", "cost", "unrelated"]
    edges = [
        ("design", "site"),
        ("geometry", "design"),
        ("quantities", "geometry"),
        ("cost", "quantities"),
    ]
    paths = dependency_paths(ids, edges, ["site"])
    assert paths == {
        "design": ["site", "design"],
        "geometry": ["site", "design", "geometry"],
        "quantities": ["site", "design", "geometry", "quantities"],
        "cost": ["site", "design", "geometry", "quantities", "cost"],
    }
    assert "site" not in paths
    assert "unrelated" not in paths


def test_dependency_paths_are_deterministic_with_multiple_roots_and_diamond_graph():
    ids = ["a", "b", "c", "d", "e"]
    edges = [("c", "a"), ("c", "b"), ("d", "c"), ("e", "d")]
    first = dependency_paths(ids, edges, ["b", "a"], include_roots=True)
    second = dependency_paths(ids, list(reversed(edges)), ["a", "b"], include_roots=True)
    assert first == second
    assert first["c"] == ["a", "c"]


def test_dependency_paths_terminate_on_cycles():
    ids = ["a", "b", "c"]
    edges = [("b", "a"), ("c", "b"), ("a", "c")]
    paths = dependency_paths(ids, edges, ["a"], include_roots=True)
    assert paths == {"a": ["a"], "b": ["a", "b"], "c": ["a", "b", "c"]}


def test_dependency_paths_reject_out_of_scope_changed_artifact():
    with pytest.raises(ValueError, match="belong to the scoped dependency graph"):
        dependency_paths(["a", "b"], [("b", "a")], ["other"])

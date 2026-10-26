from app.domains.lifecycle.dependency_paths import shortest_dependency_path


def test_shortest_dependency_path_is_deterministic():
    graph = {"a": {"c", "b"}, "b": {"d"}, "c": {"d"}, "d": set()}
    assert shortest_dependency_path(graph, "a", "d") == ("a", "b", "d")
    assert shortest_dependency_path(graph, "a", "z") == ()

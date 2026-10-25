from app.domains.commands.dependency_graph import DependencyEdge, graph_from_edges


def test_graph_returns_deterministic_dependencies_and_dependents() -> None:
    graph = graph_from_edges(["a", "b", "c"], [DependencyEdge("a", "b", "feeds"), DependencyEdge("a", "c", "invalidates")])
    assert graph.dependents_of("a") == ("b", "c")
    assert graph.dependencies_of("b") == ("a",)


def test_graph_rejects_unknown_edge_nodes() -> None:
    try:
        graph_from_edges(["a"], [DependencyEdge("a", "missing", "feeds")])
    except ValueError as exc:
        assert "unknown node" in str(exc)
    else:
        raise AssertionError("expected graph validation failure")

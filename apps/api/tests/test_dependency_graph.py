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


def test_dependency_graph_orders_dependencies_deterministically() -> None:
    graph = graph_from_edges(
        ["geometry", "analysis", "drawings"],
        [
            DependencyEdge("geometry", "drawings", "derived"),
            DependencyEdge("geometry", "analysis", "derived"),
            DependencyEdge("analysis", "drawings", "derived"),
        ],
    )
    assert graph.topological_order() == ("geometry", "analysis", "drawings")


def test_dependency_graph_rejects_cycles() -> None:
    graph = graph_from_edges(
        ["a", "b"],
        (DependencyEdge("a", "b", "derived"), DependencyEdge("b", "a", "derived")),
    )
    try:
        graph.validate()
    except ValueError as exc:
        assert "cycle" in str(exc)
    else:
        raise AssertionError("expected cycle rejection")


def test_dependency_graph_rejects_duplicate_edges() -> None:
    graph = graph_from_edges(
        ["a", "b"],
        (DependencyEdge("a", "b", "derived"), DependencyEdge("a", "b", "derived")),
    )
    try:
        graph.validate()
    except ValueError as exc:
        assert "edges" in str(exc)
    else:
        raise AssertionError("expected duplicate-edge rejection")

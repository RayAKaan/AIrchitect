import pytest

from app.domains.commands.dependency_graph import DependencyEdge, graph_from_edges


def test_graph_returns_deterministic_dependencies_and_dependents() -> None:
    graph = graph_from_edges(["a", "b", "c"], [DependencyEdge("a", "b", "feeds"), DependencyEdge("a", "c", "invalidates")])
    assert graph.dependents_of("a") == ("b", "c")
    assert graph.dependencies_of("b") == ("a",)


def test_graph_rejects_unknown_edge_nodes() -> None:
    with pytest.raises(ValueError, match="unknown node"):
        graph_from_edges(["a"], [DependencyEdge("a", "missing", "feeds")])


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
    with pytest.raises(ValueError, match="cycle"):
        graph_from_edges(
            ["a", "b"],
            (DependencyEdge("a", "b", "derived"), DependencyEdge("b", "a", "derived")),
        )


def test_dependency_graph_rejects_duplicate_edges() -> None:
    with pytest.raises(ValueError, match="edges"):
        graph_from_edges(
            ["a", "b"],
            (DependencyEdge("a", "b", "derived"), DependencyEdge("a", "b", "derived")),
        )

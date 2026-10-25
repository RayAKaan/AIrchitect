from app.domains.commands.dependency_graph import DependencyEdge, graph_from_edges
from app.domains.commands.regeneration_graph import plan_regeneration


def test_regeneration_propagates_and_orders_dependencies() -> None:
    graph = graph_from_edges(["site", "building", "drawings"], [DependencyEdge("site", "building", "invalidates"), DependencyEdge("building", "drawings", "invalidates")])
    steps = plan_regeneration(graph, ("site",))
    assert tuple(step.node_id for step in steps) == ("site", "building", "drawings")


def test_regeneration_rejects_unknown_change() -> None:
    graph = graph_from_edges(["site"], [])
    try:
        plan_regeneration(graph, ("missing",))
    except ValueError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("expected unknown-node rejection")

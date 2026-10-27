from app.domains.regulatory.impact import ChangedNode, calculate_regulatory_impact


def test_geometry_change_invalidates_regulatory_outputs():
    result = calculate_regulatory_impact(
        "rev-1",
        (ChangedNode(node_id="wall-1", artifact_type="wall", changed_fields=("length",)),),
    )
    assert set(result.impacted_targets) == {"regulatory-findings", "regulatory-evidence", "regulatory-verification"}
    assert "spatial-facts-changed" in result.invalidations[0].reasons


def test_applicability_change_is_explicit_and_deterministic():
    node = ChangedNode(node_id="project-1", artifact_type="project", changed_fields=("jurisdiction",))
    first = calculate_regulatory_impact("rev-1", (node,))
    second = calculate_regulatory_impact("rev-1", (node,))
    assert "applicability-context-changed" in first.invalidations[0].reasons
    assert first.impact_hash == second.impact_hash


def test_unrelated_artifact_does_not_invalidate_regulatory_state():
    result = calculate_regulatory_impact("rev-1", (ChangedNode(node_id="note-1", artifact_type="comment"),))
    assert result.impacted_targets == ()
    assert all(item.status == "unaffected" for item in result.invalidations)

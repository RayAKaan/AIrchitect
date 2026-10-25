from app.domains.commands.invalidation import invalidations_for
from app.domains.commands.regeneration import RegenerationPlan


def test_invalidations_follow_regeneration_order():
    plan = RegenerationPlan("cmd-1", "hash-1", ("analysis", "parametric_geometry_intents"), True)
    result = invalidations_for(plan)
    assert [item.group for item in result] == ["parametric_geometry_intents", "analysis"]
    assert all(item.source_revision_hash == "hash-1" for item in result)

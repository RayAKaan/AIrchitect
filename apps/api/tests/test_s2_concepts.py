from app.domains.design.strategies import STRATEGIES


def test_s2_has_three_materially_distinct_strategy_families():
    ids = [strategy.id for strategy in STRATEGIES]
    assert ids == ["balanced", "compact", "low_rise"]
    assert len({strategy.name for strategy in STRATEGIES}) == 3

import pytest

from app.domains.regulatory.checks import FactValue, evaluate_rule_pack
from app.domains.regulatory.rulepacks import RuleDefinition, RulePack


def _pack() -> RulePack:
    return RulePack(
        pack_id="screening",
        profile_id="jurisdiction-neutral",
        version="1.0.0",
        source_refs=("reviewed-source:screening",),
        rules=(
            RuleDefinition(
                rule_id="height-max",
                title="Maximum height",
                subject="building.height_m",
                check_type="numeric_max",
                expected=20,
                unit="m",
                source_refs=("reviewed-source:height",),
            ),
            RuleDefinition(
                rule_id="accessible",
                title="Accessibility provided",
                subject="building.accessible",
                check_type="boolean",
                expected=True,
                source_refs=("reviewed-source:accessibility",),
            ),
        ),
    )


def test_checks_produce_pass_fail_and_deterministic_hash():
    pack = _pack()
    result = evaluate_rule_pack(pack, {"building.height_m": 18, "building.accessible": True})
    assert [item.status for item in result.findings] == ["pass", "pass"]
    assert result.evaluation_hash == evaluate_rule_pack(pack, {"building.height_m": 18, "building.accessible": True}).evaluation_hash


def test_missing_input_and_unit_mismatch_are_explicit():
    pack = _pack()
    result = evaluate_rule_pack(pack, {"building.height_m": FactValue(value=25, unit="ft")})
    assert result.findings[0].status == "invalid_input"
    assert result.findings[1].status == "missing_input"


def test_catalog_only_pack_cannot_execute():
    from app.domains.regulatory.rulepacks import SBC_2024_CATALOG

    with pytest.raises(ValueError, match="Catalog-only"):
        evaluate_rule_pack(SBC_2024_CATALOG, {})

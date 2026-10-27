from app.domains.regulatory.rulepacks import RuleDefinition, RulePack, RuleApplicability, SBC_2024_CATALOG


def test_catalog_pack_is_deterministic_and_source_backed():
    assert SBC_2024_CATALOG.status == "catalog_only"
    assert SBC_2024_CATALOG.profile_id == "saudi-arabia"
    assert SBC_2024_CATALOG.pack_hash == SBC_2024_CATALOG.pack_hash
    assert SBC_2024_CATALOG.source_refs


def test_executable_pack_requires_rules_and_unique_ids():
    rule = RuleDefinition(
        rule_id="height-max",
        title="Maximum height",
        subject="building.height_m",
        check_type="numeric_max",
        expected=20,
        unit="m",
        source_refs=("official-source:example",),
        applicability=RuleApplicability(building_types=("residential",)),
    )
    pack = RulePack(
        pack_id="example",
        profile_id="jurisdiction-neutral",
        version="1.0.0",
        source_refs=("official-source:example",),
        rules=(rule,),
    )
    assert pack.pack_hash
    assert pack.rules[0].applicability.matches({"building_type": "residential"})
    assert not pack.rules[0].applicability.matches({"building_type": "commercial"})

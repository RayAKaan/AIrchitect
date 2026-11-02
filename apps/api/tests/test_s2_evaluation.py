from app.domains.design.evaluation import evaluate_alternatives


def alternative(identifier, status, footprint, height, open_site, gfa, target, checks):
    return {
        "id": identifier,
        "status": status,
        "metrics": {
            "building_footprint_m2": footprint,
            "building_height_m": height,
            "open_site_area_m2": open_site,
            "gross_floor_area_m2": gfa,
            "program_target_gfa_m2": target,
        },
        "constraint_results": checks,
    }


def test_evaluation_exposes_constraint_summary_and_pareto_tradeoffs():
    alternatives = [
        alternative("balanced", "VALID", 500, 20, 500, 1000, 1000, [
            {"status": "PASS"}, {"status": "PASS"}, {"status": "UNKNOWN"},
        ]),
        alternative("compact", "VALID", 400, 24, 600, 950, 1000, [
            {"status": "PASS"}, {"status": "FAIL"},
        ]),
        alternative("weak", "VALID", 600, 30, 400, 850, 1000, [
            {"status": "PASS"},
        ]),
    ]

    evaluated = {item["id"]: item["evaluation"] for item in evaluate_alternatives(alternatives)}

    assert evaluated["balanced"]["constraint_summary"] == {"pass": 2, "fail": 0, "unknown": 1}
    assert evaluated["balanced"]["pareto_status"] == "PARETO_FRONTIER"
    assert evaluated["compact"]["pareto_status"] == "PARETO_FRONTIER"
    assert evaluated["weak"]["pareto_status"] == "DOMINATED"
    assert set(evaluated["weak"]["dominated_by"]) == {"balanced", "compact"}
    assert "score" not in evaluated["balanced"]


def test_invalid_or_stale_alternatives_are_not_comparable():
    alternatives = [
        alternative("valid", "VALID", 500, 20, 500, 1000, 1000, [{"status": "PASS"}]),
        alternative("invalid", "INVALID", 900, 40, 100, 1300, 1000, [{"status": "FAIL"}]),
        alternative("stale", "STALE", 400, 18, 600, 950, 1000, [{"status": "PASS"}]),
    ]

    evaluated = {item["id"]: item["evaluation"] for item in evaluate_alternatives(alternatives)}

    assert evaluated["valid"]["comparable"] is True
    assert evaluated["invalid"]["comparable"] is False
    assert evaluated["stale"]["comparable"] is False
    assert evaluated["invalid"]["pareto_status"] == "NOT_COMPARABLE"
    assert evaluated["stale"]["pareto_status"] == "NOT_COMPARABLE"


def test_evaluation_never_claims_one_weighted_optimum():
    item = alternative("only", "VALID", 500, 20, 500, 1000, 1000, [])
    evaluated = evaluate_alternatives([item])[0]["evaluation"]
    assert evaluated["method"] == "transparent_multi_criteria_pareto_v1"
    assert "No weighted overall score" in evaluated["note"]

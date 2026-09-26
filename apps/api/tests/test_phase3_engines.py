import copy
import pytest
from app.domains.engineering.engines import (CostEngine,EngineeringError,EngineeringValidationEngine,QuantityEngine,
 RegulatoryEngine,StaticRulesetProvider,StructuralConceptEngine)

def inputs(floors=6):
 w,d,h=30.,40.,floors*4.;area=w*d
 ir={"site":{"dimensions":{"width":50.,"depth":50.,"area":2500.}},"masses":[{"dimensions":{"width":w,"depth":d,"height":h}}],"floor_plates":[{"dimensions":{"area":area}} for _ in range(floors)],"cores":[{"dimensions":{"width":6.,"depth":8.,"height":h}}],"structural_grids":[{"dimensions":{"x_spacing":7.5,"y_spacing":8.,"x_bays":4.,"y_bays":5.}}],"parking":{"capacity":40}}
 world={"site":{"location":{"country":"Saudi Arabia"}},"building":{"use":"commercial_retail"}}
 alt={"world_hash":"w"*64,"design_hash":"d"*64,"geometry_hash":"g"*64,"metrics":{"gross_floor_area_m2":area*floors,"building_footprint_m2":area,"site_coverage_ratio":area/2500,"floor_count":floors,"building_height_m":h,"parking_count":40},"parameters":{"setback_m":5}}
 geom={"geometry_hash":"g"*64,"geometry_ir":ir,"validation":{"valid":True}}
 return world,alt,geom

def schedule():return {"id":"rates","name":"User rates","version":"1","currency":"SAR","source_type":"USER_PROVIDED","source_reference":"user budget study","effective_date":"2026-09-01","entries":[{"item_code":"GFA_CONCEPT","category":"Other","description":"Conceptual GFA allowance","quantity_code":"GFA","unit":"m2","rate":1000.,"low_rate":900.,"high_rate":1150.,"source_type":"USER_PROVIDED","source_reference":"user budget study","effective_date":"2026-09-01"}]}

def test_quantity_formulas_units_confidence_uncertainty_and_hash():
 world,alt,geom=inputs();out=QuantityEngine().calculate(world,alt,geom);by={x["code"]:x for x in out["quantities"]}
 assert by["GFA"]["value"]==7200 and by["GFA"]["unit"]=="m2" and by["GFA"]["type"]=="EXACT_DERIVED"
 assert by["FOOTPRINT"]["value"]==1200 and by["SITE_COVERAGE"]["value"]==.48
 assert by["BUILDING_VOLUME"]["value"]==28800 and by["FLOOR_COUNT"]["value"]==6
 assert by["EXTERNAL_WALL_AREA"]["type"]=="DERIVED_APPROXIMATION" and by["EXTERNAL_WALL_AREA"]["uncertainty"]["lower_bound"]<by["EXTERNAL_WALL_AREA"]["value"]
 assert by["CONCRETE_VOLUME"]["type"]=="NOT_SUPPORTED" and by["CONCRETE_VOLUME"]["value"] is None
 assert out["validation"]["valid"] and len(out["quantity_hash"])==64
 assert QuantityEngine().calculate(world,alt,geom)["quantity_hash"]==out["quantity_hash"]

def test_quantity_invalid_geometry_is_rejected():
 world,alt,geom=inputs();geom["geometry_ir"]["site"]["dimensions"]["area"]=1000
 with pytest.raises(EngineeringError) as e:QuantityEngine().calculate(world,alt,geom)
 assert e.value.code=="QUANTITY_VALIDATION_FAILED"

def test_cost_is_exact_quantity_times_explicit_rate_with_range_and_sensitivity():
 q=QuantityEngine().calculate(*inputs());out=CostEngine().calculate(q,schedule())
 assert out["direct_cost"]==7_200_000 and out["total_cost"]==7_200_000
 assert out["low_estimate"]==6_480_000 and out["high_estimate"]==8_280_000
 assert out["breakdown"][0]["rate_provenance"]["source_type"]=="USER_PROVIDED"
 assert next(x for x in out["sensitivity"] if x["variable"]=="GFA")["total_cost_change"]==360_000
 assert CostEngine().calculate(q,schedule())["cost_hash"]==out["cost_hash"]

def test_cost_unavailable_without_matching_rates():
 q=QuantityEngine().calculate(*inputs())
 with pytest.raises(EngineeringError) as e:CostEngine().calculate(q,{**schedule(),"entries":[]})
 assert e.value.code=="RATE_UNAVAILABLE"

def test_structure_uses_persisted_grid_and_keeps_foundation_unknown():
 world,alt,geom=inputs();out=StructuralConceptEngine().calculate(world,alt,geom)
 assert out["structural_system"]=="RC_FRAME" and out["grid"]["x_spacing_m"]==7.5
 assert out["foundation_concept"]=="UNKNOWN" and "soil_conditions" in out["unknowns"]
 assert any(x["code"]=="UNKNOWN_SOIL_CONDITIONS" for x in out["warnings"])
 assert "Not safety certification" in out["disclaimer"] and len(out["concept_hash"])==64

def test_structure_warnings_are_rule_based():
 world,alt,geom=inputs(11);geom["geometry_ir"]["structural_grids"][0]["dimensions"]["x_spacing"]=10.
 out=StructuralConceptEngine().calculate(world,alt,geom)
 assert out["structural_system"]=="RC_FRAME_SHEAR_WALL"
 assert {x["code"] for x in out["warnings"]}>={"LONG_SPAN","HIGH_BUILDING_HEIGHT","UNKNOWN_SOIL_CONDITIONS"}

def test_regulatory_no_verified_rules_returns_unknown_not_pass():
 world,alt,geom=inputs();out=RegulatoryEngine().calculate(world,alt,geom)
 assert out["overall_status"]=="UNKNOWN" and out["summary"]["UNKNOWN"]==4
 assert all(x["calculation"]=="NO_RULE_AVAILABLE" and x["provenance"]["source_reference"] is None for x in out["results"])

def test_regulatory_rule_results_cover_pass_fail_unknown_and_not_applicable():
 rules={"id":"verified-test","jurisdiction":"TEST","authority":"Test Authority","version":"1","effective_date":"2026-01-01","source_type":"VERIFIED_EXTERNAL","source_reference":"test-fixture","authoritative":True,"rules":[
  {"code":"PASS","title":"Coverage","parameter":"site_coverage_ratio","operator":"lte","threshold":.5,"unit":"ratio","source_reference":"r1","effective_date":"2026-01-01"},
  {"code":"FAIL","title":"Height","parameter":"building_height_m","operator":"lte","threshold":20,"unit":"m","source_reference":"r2","effective_date":"2026-01-01"},
  {"code":"UNKNOWN","title":"Missing","parameter":"missing","operator":"lte","threshold":1,"unit":"m","source_reference":"r3","effective_date":"2026-01-01"},
  {"code":"NA","title":"Residential only","parameter":"floor_count","operator":"lte","threshold":2,"unit":"count","applicability":{"building_use":["residential"]},"source_reference":"r4","effective_date":"2026-01-01"}]}
 world,alt,geom=inputs();out=RegulatoryEngine(StaticRulesetProvider(rules)).calculate(world,alt,geom)
 assert [x["status"] for x in out["results"]]==["PASS","FAIL","UNKNOWN","NOT_APPLICABLE"]
 assert all(x["provenance"]["ruleset_version"]=="1" for x in out["results"])

def test_validation_does_not_collapse_review_states_into_approval():
 world,alt,geom=inputs();q=QuantityEngine().calculate(world,alt,geom);s=StructuralConceptEngine().calculate(world,alt,geom);r=RegulatoryEngine().calculate(world,alt,geom)
 out=EngineeringValidationEngine().calculate(geom,q,s,r,None,{"message":"Rates unavailable"})
 assert out["status"]=="REVIEW_REQUIRED"
 assert {x["status"] for x in out["checks"]}>={"PASS","WARNING","UNKNOWN"}
 assert out["human_review_required"] and len(out["validation_hash"])==64

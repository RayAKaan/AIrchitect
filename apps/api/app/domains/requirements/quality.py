"""Deterministic quality checks for preliminary building requirements."""
from __future__ import annotations
import re
from collections import defaultdict
from typing import Any, Iterable
from app.domains.requirements.extractor import RequirementCandidate
PLAUSIBILITY_LIMITS={"floor_count":(1,100),"site_area":(.000001,1_000_000_000),"target_gfa":(.000001,1_000_000_000),"floor_to_floor_height":(.000001,20),"building_height":(.000001,1000),"parking_spaces":(0,1_000_000),"budget":(0,1_000_000_000_000)}
POSITIVE_PARAMETERS={"floor_count","site_area","target_gfa","floor_to_floor_height","building_height"}
NON_NEGATIVE_PARAMETERS={"parking_spaces","budget"}
UNSUPPORTED_QUALIFIER=re.compile(r"\b(?:no more than|not more than|up to|at most|less than|fewer than|under|below|maximum(?: of)?|minimum(?: of)?|at least|no fewer than|no less than|more than|greater than|over|above|between)\b",re.I)
def _issue(code:str,severity:str,message:str,parameters:Iterable[str]=(),source_text:str|None=None)->dict[str,Any]:
    issue={"code":code,"severity":severity,"message":message,"related_parameters":sorted(set(parameters))}
    if source_text: issue["source_text"]=source_text
    return issue
def validate_requirement_candidates(candidates:list[RequirementCandidate],brief:str)->list[dict[str,Any]]:
    issues=[]; by_parameter:dict[str,list[RequirementCandidate]]=defaultdict(list)
    for c in candidates: by_parameter[c.parameter].append(c)
    for parameter,rows in sorted(by_parameter.items()):
        if len({str(r.normalized_value) for r in rows})>1:
            issues.append(_issue("CONFLICTING_VALUES","error",f"Multiple different values were found for {parameter}; confirm the intended value.",[parameter],"; ".join(r.source_text for r in rows)))
        for row in rows:
            value=row.normalized_value
            if not isinstance(value,(int,float)) or isinstance(value,bool): continue
            if parameter in POSITIVE_PARAMETERS and value<=0:
                issues.append(_issue("INVALID_NONPOSITIVE_VALUE","error",f"{parameter} must be greater than zero before it can enter the canonical model.",[parameter],row.source_text))
            elif parameter in NON_NEGATIVE_PARAMETERS and value<0:
                issues.append(_issue("INVALID_NEGATIVE_VALUE","error",f"{parameter} cannot be negative.",[parameter],row.source_text))
            limits=PLAUSIBILITY_LIMITS.get(parameter)
            if limits and not limits[0]<=value<=limits[1]:
                issues.append(_issue("IMPLAUSIBLE_VALUE","warning",f"{parameter}={value} is outside the preliminary review range {limits[0]}–{limits[1]}; verify units and intent.",[parameter],row.source_text))
            if parameter=="target_gfa" and row.confidence<1.0:
                issues.append(_issue("AMBIGUOUS_AREA_INFERENCE","warning","This area was inferred as target GFA without an explicit GFA label; confirm its meaning.",[parameter],row.source_text))
    qualifier=UNSUPPORTED_QUALIFIER.search(brief)
    if qualifier and re.search(r"\b(?:floors?|storeys?|stories|gfa|gross floor area|site area|plot area|parking spaces?|budget|sar|m²|m2|sqm)\b",brief[qualifier.start():qualifier.start()+160],re.I):
        issues.append(_issue("UNSUPPORTED_CONSTRAINT_QUALIFIER","warning","The brief contains a limit or range that the exact-value schema cannot safely represent. Clarify it before treating an extracted value as a hard constraint.",(),brief[max(0,qualifier.start()-30):min(len(brief),qualifier.start()+120)].strip()))
    exact={}
    for parameter in ("floor_count","floor_to_floor_height","building_height"):
        rows=by_parameter.get(parameter,[])
        if rows and len({str(r.normalized_value) for r in rows})==1:
            try: exact[parameter]=float(rows[0].normalized_value)
            except (TypeError,ValueError): pass
    if {"floor_count","floor_to_floor_height","building_height"}<=exact.keys():
        derived=exact["floor_count"]*exact["floor_to_floor_height"]
        if abs(derived-exact["building_height"])>.5:
            issues.append(_issue("HEIGHT_FLOOR_INCONSISTENCY","warning",f"Explicit building height ({exact['building_height']:g} m) differs from floor count × floor-to-floor height ({derived:g} m) by more than 0.5 m.",["building_height","floor_count","floor_to_floor_height"]))
    unique={}
    for item in issues: unique[(item["code"],tuple(item["related_parameters"]),item.get("source_text",""))]=item
    return [unique[k] for k in sorted(unique)]
def blocking_parameters(issues:list[dict[str,Any]])->set[str]:
    return {p for issue in issues if issue.get("severity")=="error" for p in issue.get("related_parameters",[])}
def validation_status(issues:list[dict[str,Any]])->str:
    if any(i.get("severity")=="error" for i in issues): return "BLOCKED"
    return "REVIEW_REQUIRED" if issues else "PASS"

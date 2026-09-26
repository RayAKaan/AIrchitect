from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Protocol
from app.domains.lifecycle.service import canonical_hash
from .config import DEFAULT_CONFIG,EngineeringConfig

class EngineeringError(Exception):
 def __init__(self,code:str,message:str,context:dict|None=None):self.code,self.message,self.context=code,message,context or {};super().__init__(message)

def item(code,label,value,unit,qtype,source,precision=2,uncertainty=None):
 return {"code":code,"label":label,"value":round(value,precision) if value is not None else None,"unit":unit,"source":source,"precision":precision,"type":qtype,"uncertainty":uncertainty}

class QuantityValidator:
 VALID_UNITS={"m","m2","m3","kg","count","ratio"}
 def __init__(self,config=DEFAULT_CONFIG):self.config=config
 def validate(self,output:dict,ir:dict,alternative:dict)->dict:
  by={x["code"]:x for x in output["quantities"]}; checks=[]
  def check(code,ok,actual,expected):checks.append({"code":code,"status":"PASS" if ok else "FAIL","actual":actual,"expected":expected})
  plates=ir["floor_plates"];site=ir["site"]["dimensions"];mass=ir["masses"][0]["dimensions"]
  gfa=sum(float(x["dimensions"]["area"]) for x in plates);foot=float(mass["width"])*float(mass["depth"]);coverage=foot/float(site["area"])
  check("gfa_consistency",abs(by["GFA"]["value"]-gfa)<=self.config.quantity_tolerance,by["GFA"]["value"],gfa)
  check("floor_count_consistency",by["FLOOR_COUNT"]["value"]==len(plates),by["FLOOR_COUNT"]["value"],len(plates))
  check("footprint_consistency",abs(by["FOOTPRINT"]["value"]-foot)<=.01,by["FOOTPRINT"]["value"],foot)
  check("coverage_consistency",abs(by["SITE_COVERAGE"]["value"]-coverage)<=.0001,by["SITE_COVERAGE"]["value"],coverage)
  check("volume_consistency",abs(by["BUILDING_VOLUME"]["value"]-foot*float(mass["height"]))<=.1,by["BUILDING_VOLUME"]["value"],foot*float(mass["height"]))
  metrics=alternative.get("metrics",{})
  check("alternative_gfa_consistency",abs(gfa-float(metrics.get("gross_floor_area_m2",gfa)))<=.01,gfa,metrics.get("gross_floor_area_m2"))
  check("alternative_coverage_consistency",abs(coverage-float(metrics.get("site_coverage_ratio",coverage)))<=.0001,coverage,metrics.get("site_coverage_ratio"))
  check("source_geometry_hash",output["input_geometry_hash"]==alternative["geometry_hash"],output["input_geometry_hash"],alternative["geometry_hash"])
  check("unit_validity",all(x["unit"] in self.VALID_UNITS for x in output["quantities"]),[x["unit"] for x in output["quantities"]],sorted(self.VALID_UNITS))
  check("non_negative",all(x["value"] is None or x["value"]>=0 for x in output["quantities"]),True,True)
  return {"valid":all(x["status"]=="PASS" for x in checks),"checks":checks,"errors":[x["code"] for x in checks if x["status"]=="FAIL"]}

class QuantityEngine:
 def __init__(self,config:EngineeringConfig=DEFAULT_CONFIG):self.config=config;self.validator=QuantityValidator(config)
 def calculate(self,world:dict,alternative:dict,geometry:dict)->dict:
  ir=geometry["geometry_ir"];plates=ir["floor_plates"];mass=ir["masses"][0]["dimensions"];site=ir["site"]["dimensions"]
  floor_areas=[float(x["dimensions"]["area"]) for x in plates];gfa=sum(floor_areas);foot=float(mass["width"])*float(mass["depth"]);height=float(mass["height"]);site_area=float(site["area"])
  wall=2*(float(mass["width"])+float(mass["depth"]))*height;ratio=self.config.external_wall_uncertainty_ratio
  core_area=sum(float(c["dimensions"]["width"])*float(c["dimensions"]["depth"])*len(plates) for c in ir.get("cores",[]))
  quantities=[item("GFA","Gross Floor Area",gfa,"m2","EXACT_DERIVED","sum(GeometryIR.floor_plates.area)"),
   item("FLOOR_PLATE_AREA","Floor Plate Area",sum(floor_areas)/len(floor_areas),"m2","EXACT_DERIVED","mean(GeometryIR.floor_plates.area)"),
   item("FOOTPRINT","Building Footprint",foot,"m2","EXACT_DERIVED","GeometryIR.mass.width × depth"),
   item("BUILDING_VOLUME","Building Envelope Volume",foot*height,"m3","EXACT_DERIVED","footprint × mass height"),
   item("FLOOR_COUNT","Number of Floors",float(len(plates)),"count","EXACT_DERIVED","count(GeometryIR.floor_plates)",0),
   item("EXTERNAL_WALL_AREA","Approximate External Wall Area",wall,"m2","DERIVED_APPROXIMATION","rectangular mass perimeter × height",2,{"lower_bound":round(wall*(1-ratio),2),"upper_bound":round(wall*(1+ratio),2),"basis":"±5% configuration band around rectangular massing perimeter; excludes openings and articulation","confidence":"LOW"}),
   item("ROOF_AREA","Approximate Roof Area",floor_areas[-1],"m2","EXACT_DERIVED","top GeometryIR floor plate area"),
   item("CORE_AREA","Cumulative Conceptual Core Area",core_area,"m2","DERIVED_APPROXIMATION","conceptual core footprint × floor count"),
   item("PARKING_CAPACITY","Parking Capacity",ir.get("parking",{}).get("capacity"),"count","EXACT_DERIVED" if ir.get("parking",{}).get("capacity") is not None else "UNKNOWN","GeometryIR parking capacity",0),
   item("SITE_COVERAGE","Site Coverage",foot/site_area,"ratio","EXACT_DERIVED","footprint / site area",4),
   item("OPEN_SITE_AREA","Open Site Area",site_area-foot,"m2","EXACT_DERIVED","site area - footprint")]
  quantities += [item("CONCRETE_VOLUME","Concrete Volume",None,"m3","NOT_SUPPORTED","No member dimensions or slab specification"),item("REINFORCEMENT_MASS","Reinforcement Mass",None,"kg","NOT_SUPPORTED","No structural design")]
  out={"schema_version":"1.0.0","quantities":quantities,"assumptions":[{"code":"RECTANGULAR_ENVELOPE","statement":"External wall area uses the persisted rectangular conceptual mass perimeter."}],"unknowns":[x["code"] for x in quantities if x["type"] in {"UNKNOWN","NOT_SUPPORTED"}],"uncertainty":{"classification":"PRELIMINARY","approximation_items":[x["code"] for x in quantities if x["type"] in {"DERIVED_APPROXIMATION","ASSUMPTION_BASED"}]},"input_world_model_hash":alternative["world_hash"],"input_design_hash":alternative["design_hash"],"input_geometry_hash":geometry["geometry_hash"],"engine_name":self.config.quantity_engine_name,"engine_version":self.config.quantity_engine_version,"config_version":self.config.config_version}
  out["validation"]=self.validator.validate(out,ir,{**alternative,"geometry_hash":geometry["geometry_hash"]})
  if not out["validation"]["valid"]:raise EngineeringError("QUANTITY_VALIDATION_FAILED","Derived quantities failed consistency validation",{"errors":out["validation"]["errors"]})
  out["quantity_hash"]=canonical_hash({"inputs":[out["input_world_model_hash"],out["input_design_hash"],out["input_geometry_hash"]],"engine":out["engine_version"],"config":self.config.canonical(),"quantities":quantities})
  return out

class RateProvider(Protocol):
 def get_schedule(self)->dict:...
@dataclass
class StaticRateProvider:
 schedule:dict
 def get_schedule(self):return self.schedule
class UserProvidedRateProvider(StaticRateProvider):pass
class VerifiedScheduleProvider(StaticRateProvider):pass

def schedule_hash(schedule:dict)->str:return canonical_hash({k:schedule[k] for k in sorted(schedule) if k not in {"id","created_at"}})

class CostEngine:
 def __init__(self,config=DEFAULT_CONFIG):self.config=config
 def calculate(self,quantity:dict,schedule:dict)->dict:
  entries=schedule.get("entries",[])
  if not entries:raise EngineeringError("RATE_UNAVAILABLE","The selected rate schedule has no usable rates",{"required_input":"rate entries"})
  by={x["code"]:x for x in quantity["quantities"]};lines=[];unknowns=[]
  for r in sorted(entries,key=lambda x:x["item_code"]):
   q=by.get(r["quantity_code"])
   if not q or q["value"] is None:unknowns.append({"item_code":r["item_code"],"reason":"quantity unavailable"});continue
   if q["unit"]!=r["unit"]:raise EngineeringError("COST_CALCULATION_FAILED","Rate and quantity units do not match",{"item_code":r["item_code"],"quantity_unit":q["unit"],"rate_unit":r["unit"]})
   base=float(q["value"])*float(r["rate"]);low=float(q["value"])*float(r.get("low_rate") if r.get("low_rate") is not None else r["rate"]);high=float(q["value"])*float(r.get("high_rate") if r.get("high_rate") is not None else r["rate"])
   lines.append({"item_code":r["item_code"],"category":r["category"],"description":r["description"],"quantity_code":q["code"],"quantity":q["value"],"unit":q["unit"],"rate":r["rate"],"low_rate":r.get("low_rate"),"high_rate":r.get("high_rate"),"line_cost":round(base,2),"low_cost":round(low,2),"high_cost":round(high,2),"currency":schedule["currency"],"rate_provenance":{"source_type":r["source_type"],"source_reference":r["source_reference"],"effective_date":r["effective_date"],"schedule_version":schedule["version"]}})
  if not lines:raise EngineeringError("RATE_UNAVAILABLE","No selected rates match available derived quantities",{"available_quantities":sorted(by)})
  direct=sum(x["line_cost"] for x in lines);low=sum(x["low_cost"] for x in lines);high=sum(x["high_cost"] for x in lines)
  sensitivities=[{"variable":f"RATE:{x['item_code']}","change":"+10%","total_cost_change":round(x["line_cost"]*.1,2),"basis":"linear quantity × rate"} for x in lines]
  gfa_effect=sum(x["line_cost"]*.05 for x in lines if x["quantity_code"]=="GFA");sensitivities.append({"variable":"GFA","change":"+5%","total_cost_change":round(gfa_effect,2),"basis":"recalculate GFA-linked lines only; other quantities unchanged"})
  out={"schema_version":"1.0.0","basis":"CONCEPTUAL_QUANTITY_RATE_ESTIMATE","currency":schedule["currency"],"direct_cost":round(direct,2),"indirect_cost":0.0,"contingency":0.0,"total_cost":round(direct,2),"low_estimate":round(low,2),"high_estimate":round(high,2),"breakdown":lines,"assumptions":["No indirect cost or contingency is added unless represented by an explicit rate entry."],"unknowns":unknowns,"uncertainty":{"classification":"PRELIMINARY","range_basis":"sum of explicit rate-entry low/high values; base rate used when bounds absent","rate_schedule_source_type":schedule["source_type"]},"sensitivity":sensitivities,"input_quantity_hash":quantity["quantity_hash"],"input_rate_schedule_hash":schedule_hash(schedule),"engine_name":self.config.cost_engine_name,"engine_version":self.config.cost_engine_version,"config_version":self.config.config_version}
  out["cost_hash"]=canonical_hash({"quantity_hash":out["input_quantity_hash"],"schedule_hash":out["input_rate_schedule_hash"],"engine":out["engine_version"],"config":self.config.canonical(),"output":{k:out[k] for k in ["currency","direct_cost","total_cost","low_estimate","high_estimate","breakdown"]}})
  return out

class StructuralConceptEngine:
 DISCLAIMER="PRELIMINARY STRUCTURAL CONCEPT. Not structural design. Not construction-ready. Not safety certification. Requires qualified structural engineer review."
 def __init__(self,config=DEFAULT_CONFIG):self.config=config
 def calculate(self,world:dict,alternative:dict,geometry:dict)->dict:
  ir=geometry["geometry_ir"];mass=ir["masses"][0]["dimensions"];floors=len(ir["floor_plates"]);h=float(mass["height"]);w=float(mass["width"]);d=float(mass["depth"]);grids=ir.get("structural_grids",[]);grid=grids[0]["dimensions"] if grids else None
  maxspan=max(float(grid["x_spacing"]),float(grid["y_spacing"])) if grid else None;system="RC_FRAME_SHEAR_WALL" if floors>8 or h>35 else "RC_FRAME"
  warnings=[{"code":"UNKNOWN_SOIL_CONDITIONS","message":"No verified geotechnical information is present; foundation concept remains unknown."}]
  if maxspan is None:warnings.append({"code":"STRUCTURAL_GRID_UNKNOWN","message":"No conceptual grid is present in Geometry IR."})
  elif maxspan>self.config.long_span_m:warnings.append({"code":"LONG_SPAN","message":f"Conceptual grid span {maxspan:.2f} m exceeds the {self.config.long_span_m:.2f} m warning threshold."})
  if max(w/d,d/w)>self.config.high_aspect_ratio:warnings.append({"code":"HIGH_ASPECT_RATIO","message":"Persisted mass aspect ratio exceeds the configured conceptual threshold."})
  if h>self.config.high_building_height_m:warnings.append({"code":"HIGH_BUILDING_HEIGHT","message":"Building height exceeds the configured conceptual threshold."})
  out={"schema_version":"1.0.0","structural_system":system,"system_basis":f"deterministic conceptual classification from {floors} floors and {h:.2f} m height","grid":{"status":"CONCEPTUAL" if grid else "UNKNOWN","x_spacing_m":grid.get("x_spacing") if grid else None,"y_spacing_m":grid.get("y_spacing") if grid else None,"x_bays":grid.get("x_bays") if grid else None,"y_bays":grid.get("y_bays") if grid else None,"source":"persisted Geometry IR preliminary grid" if grid else None},"span_assumptions":{"maximum_conceptual_span_m":maxspan,"engineered":False},"vertical_system":"PRELIMINARY_FRAME_CANDIDATE","lateral_system":"PRELIMINARY_CORE_OR_SHEAR_WALL_CANDIDATE" if system=="RC_FRAME_SHEAR_WALL" else "UNKNOWN","foundation_concept":"UNKNOWN","assumptions":["Phase 2 grid is conceptual and not engineering approved.","System classification is a feasibility candidate only."],"warnings":warnings,"unknowns":["soil_conditions","loads","material_strengths","wind_and_seismic_actions","foundation_system"]+( ["lateral_system"] if system=="RC_FRAME" else []),"disclaimer":self.DISCLAIMER,"input_world_model_hash":alternative["world_hash"],"input_design_hash":alternative["design_hash"],"input_geometry_hash":geometry["geometry_hash"],"engine_name":self.config.structural_engine_name,"engine_version":self.config.structural_engine_version,"config_version":self.config.config_version}
  out["concept_hash"]=canonical_hash({"inputs":[out["input_world_model_hash"],out["input_design_hash"],out["input_geometry_hash"]],"engine":out["engine_version"],"config":self.config.canonical(),"concept":{k:out[k] for k in ["structural_system","grid","vertical_system","lateral_system","foundation_concept","warnings","unknowns"]}})
  return out

class RegulatoryRulesetProvider(Protocol):
 def get_ruleset(self,jurisdiction:str)->dict:...
class StaticRulesetProvider:
 def __init__(self,ruleset:dict):self.ruleset=ruleset
 def get_ruleset(self,jurisdiction:str):return self.ruleset
class VerifiedRulesetProvider(StaticRulesetProvider):pass
class NoVerifiedRulesProvider:
 def get_ruleset(self,jurisdiction:str):return {"id":None,"jurisdiction":jurisdiction or "UNKNOWN","authority":"UNCONFIGURED","version":"no-verified-rules-v1","effective_date":None,"source_type":"NONE","source_reference":None,"authoritative":False,"rules":[]}

class RegulatoryEngine:
 EXPECTED=[("MAXIMUM_HEIGHT","Maximum permitted height","building_height_m","m"),("PARKING_REQUIREMENT","Parking requirement","parking_count","count"),("SITE_COVERAGE","Site coverage","site_coverage_ratio","ratio"),("SETBACK","Setback","setback_m","m")]
 def __init__(self,provider:RegulatoryRulesetProvider|None=None,config=DEFAULT_CONFIG):self.provider=provider or NoVerifiedRulesProvider();self.config=config
 def _eval(self,rule,facts):
  app=rule.get("applicability",{});use=app.get("building_use")
  if use and facts.get("building_use") is not None and facts["building_use"] not in use:return "NOT_APPLICABLE","NOT_APPLICABLE",facts.get(rule["parameter"]),"Rule does not apply to this building classification."
  if use and facts.get("building_use") is None:return "UNKNOWN","UNKNOWN",None,"Building classification required to determine applicability."
  val=facts.get(rule["parameter"])
  if val is None:return "APPLICABLE","UNKNOWN",None,"Required input is unknown."
  op=rule["operator"];threshold=rule.get("threshold")
  if op=="exists":passed=val is not None
  elif op=="in":passed=val in threshold
  elif op=="eq":passed=val==threshold
  else:passed={"lte":val<=threshold,"lt":val<threshold,"gte":val>=threshold,"gt":val>threshold}[op]
  return "APPLICABLE","PASS" if passed else "FAIL",val,f"Observed value {val} {op} threshold {threshold}."
 def calculate(self,world:dict,alternative:dict,geometry:dict)->dict:
  jurisdiction=world.get("site",{}).get("location",{}).get("country") or "UNKNOWN";ruleset=self.provider.get_ruleset(jurisdiction)
  metrics=alternative["metrics"];facts={**metrics,"building_use":world.get("building",{}).get("use"),"setback_m":alternative.get("parameters",{}).get("setback_m")}
  results=[]
  if ruleset.get("rules"):
   for r in ruleset["rules"]:
    applicability,status,observed,reason=self._eval(r,facts);results.append({"rule_code":r["code"],"title":r["title"],"applicability":applicability,"status":status,"observed":observed,"threshold":r.get("threshold"),"unit":r.get("unit"),"calculation":f"{r['parameter']} {r['operator']} {r.get('threshold')}","reason":reason,"provenance":{"ruleset_id":ruleset.get("id"),"ruleset_version":ruleset["version"],"jurisdiction":ruleset["jurisdiction"],"source_reference":r.get("source_reference"),"effective_date":r.get("effective_date")}})
  else:
   for code,title,param,unit in self.EXPECTED:results.append({"rule_code":code,"title":title,"applicability":"UNKNOWN","status":"UNKNOWN","observed":facts.get(param),"threshold":None,"unit":unit,"calculation":"NO_RULE_AVAILABLE","reason":"No verified applicable rule is configured; no compliance conclusion is made.","provenance":{"ruleset_id":None,"ruleset_version":ruleset["version"],"jurisdiction":jurisdiction,"source_reference":None,"effective_date":None}})
  counts={s:sum(x["status"]==s for x in results) for s in ["PASS","FAIL","UNKNOWN","NOT_APPLICABLE"]};overall="FAIL" if counts["FAIL"] else "UNKNOWN" if counts["UNKNOWN"] else "PASS"
  out={"schema_version":"1.0.0","jurisdiction":jurisdiction,"ruleset":{k:ruleset.get(k) for k in ["id","authority","version","effective_date","source_type","source_reference","authoritative"]},"results":results,"summary":counts,"overall_status":overall,"notice":"This evaluation is preliminary and is not regulatory approval or a compliance certificate.","input_world_model_hash":alternative["world_hash"],"input_design_hash":alternative["design_hash"],"input_geometry_hash":geometry["geometry_hash"],"engine_name":self.config.regulatory_engine_name,"engine_version":self.config.regulatory_engine_version,"config_version":self.config.config_version}
  out["regulatory_hash"]=canonical_hash({"inputs":[out["input_world_model_hash"],out["input_design_hash"],out["input_geometry_hash"]],"ruleset":out["ruleset"],"engine":out["engine_version"],"results":results})
  return out

class EngineeringValidationEngine:
 def __init__(self,config=DEFAULT_CONFIG):self.config=config
 def calculate(self,geometry:dict,quantity:dict,structure:dict,regulatory:dict,cost:dict|None,cost_error:dict|None=None)->dict:
  checks=[]
  def add(category,code,status,severity,message,source):checks.append({"category":category,"code":code,"status":status,"severity":severity,"message":message,"source_artifact":source,"evidence":[]})
  gv=geometry.get("validation",{});add("GEOMETRY","GEOMETRY_VALID", "PASS" if gv.get("valid") else "FAIL","ERROR" if not gv.get("valid") else "INFO","Persisted Phase 2 geometry validation status.","geometry")
  qv=quantity["validation"];add("QUANTITIES","QUANTITY_CONSISTENCY","PASS" if qv["valid"] else "FAIL","ERROR" if not qv["valid"] else "INFO","Quantity-to-geometry consistency checks.","quantity")
  if cost:add("COST","COST_REPRODUCIBLE","PASS","INFO","Cost lines reproduce from quantity × explicit rate.","cost")
  else:add("COST","COST_UNAVAILABLE","WARNING","WARNING",(cost_error or {}).get("message","No rate schedule selected."),"quantity")
  add("STRUCTURE","STRUCTURAL_REVIEW_REQUIRED","WARNING","WARNING",structure["disclaimer"],"structural")
  regstatus=regulatory["overall_status"];add("REGULATIONS","REGULATORY_EVALUATION",regstatus,"ERROR" if regstatus=="FAIL" else "WARNING","Regulatory checks include explicit unknown/no-rule states and are not approval.","regulatory")
  statuses={c["status"] for c in checks};overall="BLOCKED" if "FAIL" in statuses else "REVIEW_REQUIRED"
  inputs={"geometry_hash":geometry["geometry_hash"],"quantity_hash":quantity["quantity_hash"],"cost_hash":cost.get("cost_hash") if cost else None,"structural_hash":structure["concept_hash"],"regulatory_hash":regulatory["regulatory_hash"]}
  out={"schema_version":"1.0.0","status":overall,"checks":checks,"summary":{s:sum(x["status"]==s for x in checks) for s in ["PASS","FAIL","WARNING","UNKNOWN"]},"input_hashes":inputs,"human_review_required":True,"limitations":["Validation is not approval, engineering certification, regulatory authorization, or permission to construct."],"engine_name":self.config.validation_engine_name,"engine_version":self.config.validation_engine_version,"config_version":self.config.config_version}
  out["validation_hash"]=canonical_hash({"inputs":inputs,"engine":out["engine_version"],"checks":checks})
  return out

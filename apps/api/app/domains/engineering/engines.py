from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Protocol
from app.domains.lifecycle.service import canonical_hash
from .config import DEFAULT_CONFIG,EngineeringConfig

class EngineeringError(Exception):
 def __init__(self,code:str,message:str,context:dict|None=None):self.code,self.message,self.context=code,message,context or {};super().__init__(message)

def item(code,label,value,unit,qtype,source,precision=2,uncertainty=None):
 return {"code":code,"label":label,"value":round(value,precision) if value is not None else None,"unit":unit,"source":source,"precision":precision,"type":qtype,"uncertainty":uncertainty}

# Slack allowed when re-adding the worker's own per-solid measurements. Both sides
# are sums of the same JSON doubles, so this absorbs float re-association and
# nothing else; a genuine disagreement between them is orders of magnitude larger.
MEASURED_SUM_RELATIVE_TOLERANCE=1e-9
# Relative gap between a measured volume and the design engine's analytical estimate
# above which the divergence is reported. It stays a warning rather than a failure:
# the measurement is authoritative, so a divergence is a fact about the design, not
# a fault in the geometry, and failing here would throw away the better number.
MEASURED_DIVERGENCE_WARN=0.02

def _close(a,b):return abs(a-b)<=MEASURED_SUM_RELATIVE_TOLERANCE*max(abs(a),abs(b))

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
  return {"valid":all(x["status"]=="PASS" for x in checks),"checks":checks,"errors":[x["code"] for x in checks if x["status"]=="FAIL"],"warnings":[]}
 def _document(self,checks,warnings):return {"valid":all(x["status"]=="PASS" for x in checks),"checks":checks,"errors":[x["code"] for x in checks if x["status"]=="FAIL"],"warnings":warnings}
 def validate_solids(self,output:dict,geometry:dict,alternative:dict)->dict:
  """Cross-check the worker's reported measurements against each other and against the solid.

  Nothing here compares a measured value to a declared one. A solid is either
  self-consistent or it is not, and that is a property of the geometry alone, so
  every check below can be answered without consulting the design engine. The
  declared figures are a separate topic, reported on the output as warnings.
  """
  by={x["code"]:x for x in output["quantities"]};checks=[];warnings=[]
  def check(code,ok,actual,expected):checks.append({"code":code,"status":"PASS" if ok else "FAIL","actual":actual,"expected":expected})
  solids=geometry["measurements"];volume=geometry.get("combined_volume_m3");area=geometry.get("combined_area_m2");bbox=geometry.get("combined_bounding_box")
  if volume is None or area is None:
   check("measured_totals_present",False,{"volume_m3":volume,"area_m2":area},"both a volume and an area");return self._document(checks,warnings)
  check("measured_totals_present",True,{"volume_m3":volume,"area_m2":area},"both a volume and an area")
  check("measured_volume_positive",volume>0,volume,"> 0")
  check("measured_area_positive",area>0,area,"> 0")
  if bbox:
   extents=[float(bbox["max"][i])-float(bbox["min"][i]) for i in range(3)];box=extents[0]*extents[1]*extents[2]
   # A solid cannot occupy more space than the box that encloses it. This is the one
   # invariant that catches a worker reporting a total in the wrong unit, which no
   # amount of self-consistency between the per-solid rows would reveal.
   check("volume_within_bounding_box",0<volume<=box,volume,f"<= {round(box,6)}")
   check("footprint_matches_bounding_box",abs(by["FOOTPRINT"]["value"]-extents[0]*extents[1])<=.01,by["FOOTPRINT"]["value"],round(extents[0]*extents[1],6))
   check("height_matches_bounding_box",abs(by["BUILDING_HEIGHT"]["value"]-extents[2])<=.001,by["BUILDING_HEIGHT"]["value"],round(extents[2],6))
  else:check("bounding_box_present",False,None,"a bounding box")
  summed_v=sum(float(s["volume_m3"]) for s in solids);summed_a=sum(float(s["surface_area_m2"]) for s in solids)
  check("combined_volume_matches_solids",_close(summed_v,volume),volume,round(summed_v,6))
  check("combined_area_matches_solids",_close(summed_a,area),area,round(summed_a,6))
  # An open shell has a computable volume but is not a solid. Reporting one as a
  # measured building volume would be a category error, so the run is refused.
  open_solids=[s["id"] for s in solids if not (s.get("is_valid") and s.get("is_closed"))]
  check("solids_closed",not open_solids,open_solids or "every solid valid and closed","every solid valid and closed")
  for code,key in (("SOLID_COUNT","solid_count"),("FACE_COUNT","face_count"),("EDGE_COUNT","edge_count"),("VERTEX_COUNT","vertex_count")):
   total=sum(int(s[key]) for s in solids)
   check(f"{key}_matches_solids",by[code]["value"]==total,by[code]["value"],total)
  check("source_geometry_hash",output["input_geometry_hash"]==alternative["geometry_hash"],output["input_geometry_hash"],alternative["geometry_hash"])
  check("unit_validity",all(x["unit"] in self.VALID_UNITS for x in output["quantities"]),[x["unit"] for x in output["quantities"]],sorted(self.VALID_UNITS))
  check("non_negative",all(x["value"] is None or x["value"]>=0 for x in output["quantities"]),True,True)
  # A declared input that is absent must read as unknown, not as zero. Zero would
  # silently become a cost of nothing rather than an unanswered question. This is a
  # warning rather than a failure: a missing programme figure is the programme's
  # omission, and refusing to report the volume the kernel did measure because a
  # floor area was never declared would trade a good number for none.
  for code,key in (("GFA","gross_floor_area_m2"),("FLOOR_COUNT","floor_count"),("SITE_AREA","site_area_m2")):
   if by[code]["value"] is None:
    warnings.append({"code":"DECLARED_INPUT_ABSENT","status":"WARNING","quantity_code":code,"detail":f"The design alternative declares no {key}, so this quantity is unknown rather than zero. Quantities derived from it are unknown too, and any rate schedule line that needs them is recorded as an unknown."})
  declared=(alternative.get("metrics") or {}).get("building_volume_m3")
  if declared:
   d=float(declared);drift=abs(volume-d)/abs(d) if d else None
   if drift is not None and drift>MEASURED_DIVERGENCE_WARN:
    warnings.append({"code":"DECLARED_VOLUME_DIVERGENCE","status":"WARNING","measured_m3":round(volume,6),"declared_m3":round(d,6),"relative_difference":round(drift,6),"authoritative":"measured","detail":"The design engine's analytical volume and the volume measured on the solid disagree. The measured value is reported; the declared figure is retained for comparison and was not used."})
  return self._document(checks,warnings)

class QuantityEngine:
 def __init__(self,config:EngineeringConfig=DEFAULT_CONFIG):self.config=config;self.validator=QuantityValidator(config)
 def calculate(self,world:dict,alternative:dict,geometry:dict)->dict:
  if geometry.get("source")=="CAD_BREP":return self.from_solids(world,alternative,geometry)
  return self.from_ir(world,alternative,geometry)
 def from_ir(self,world:dict,alternative:dict,geometry:dict)->dict:
  ir=geometry["geometry_ir"];plates=ir["floor_plates"];mass=ir["masses"][0]["dimensions"];site=ir["site"]["dimensions"]
  floor_areas=[float(x["dimensions"]["area"]) for x in plates];gfa=sum(floor_areas);foot=float(mass["width"])*float(mass["depth"]);height=float(mass["height"]);site_area=float(site["area"])
  wall=2*(float(mass["width"])+float(mass["depth"]))*height;ratio=self.config.external_wall_uncertainty_ratio
  core_area=sum(float(c["dimensions"]["width"])*float(c["dimensions"]["depth"])*len(plates) for c in ir.get("cores",[]))
  quantities=[item("GFA","Gross Floor Area",gfa,"m2","EXACT_DERIVED","sum(GeometryIR.floor_plates.area)"),
   item("FLOOR_PLATE_AREA","Floor Plate Area",sum(floor_areas)/len(floor_areas),"m2","EXACT_DERIVED","mean(GeometryIR.floor_plates.area)"),
    item("FOOTPRINT","Building Footprint",foot,"m2","EXACT_DERIVED","GeometryIR.mass.width × depth"),
    item("BUILDING_HEIGHT","Overall Building Height",height,"m","EXACT_DERIVED","GeometryIR.mass.height",3),
    item("BUILDING_VOLUME","Building Envelope Volume",foot*height,"m3","EXACT_DERIVED","footprint × mass height"),
   item("FLOOR_COUNT","Number of Floors",float(len(plates)),"count","EXACT_DERIVED","count(GeometryIR.floor_plates)",0),
   item("EXTERNAL_WALL_AREA","Approximate External Wall Area",wall,"m2","DERIVED_APPROXIMATION","rectangular mass perimeter × height",2,{"lower_bound":round(wall*(1-ratio),2),"upper_bound":round(wall*(1+ratio),2),"basis":"±5% configuration band around rectangular massing perimeter; excludes openings and articulation","confidence":"LOW"}),
   item("ROOF_AREA","Approximate Roof Area",floor_areas[-1],"m2","EXACT_DERIVED","top GeometryIR floor plate area"),
   item("CORE_AREA","Cumulative Conceptual Core Area",core_area,"m2","DERIVED_APPROXIMATION","conceptual core footprint × floor count"),
   item("PARKING_CAPACITY","Parking Capacity",ir.get("parking",{}).get("capacity"),"count","EXACT_DERIVED" if ir.get("parking",{}).get("capacity") is not None else "UNKNOWN","GeometryIR parking capacity",0),
   item("SITE_COVERAGE","Site Coverage",foot/site_area,"ratio","EXACT_DERIVED","footprint / site area",4),
   item("OPEN_SITE_AREA","Open Site Area",site_area-foot,"m2","EXACT_DERIVED","site area - footprint")]
  quantities += [item("CONCRETE_VOLUME","Concrete Volume",None,"m3","NOT_SUPPORTED","No member dimensions or slab specification"),item("REINFORCEMENT_MASS","Reinforcement Mass",None,"kg","NOT_SUPPORTED","No structural design")]
  out={"schema_version":"1.0.0","quantities":quantities,"assumptions":[{"code":"RECTANGULAR_ENVELOPE","statement":"External wall area uses the persisted rectangular conceptual mass perimeter."}],"unknowns":[x["code"] for x in quantities if x["type"] in {"UNKNOWN","NOT_SUPPORTED"}],"uncertainty":{"classification":"PRELIMINARY","approximation_items":[x["code"] for x in quantities if x["type"] in {"DERIVED_APPROXIMATION","ASSUMPTION_BASED"}]},"input_world_model_hash":alternative["world_hash"],"input_design_hash":alternative["design_hash"],"input_geometry_hash":geometry["geometry_hash"],"measurement_provenance":{"geometry_source":"LEGACY_IR","measured_quantities":[],"declared_quantities":[],"approximated_quantities":[x["code"] for x in quantities if x["type"] in {"DERIVED_APPROXIMATION","ASSUMPTION_BASED"}],"notice":"Every value here is computed from a persisted GeometryIR description of the massing. No solid was built and nothing was measured on one, so these are dimensions read back from parameters, not quantities taken off a B-rep."},"engine_name":self.config.quantity_engine_name,"engine_version":self.config.quantity_engine_version,"config_version":self.config.config_version}
  out["validation"]=self.validator.validate(out,ir,{**alternative,"geometry_hash":geometry["geometry_hash"]})
  if not out["validation"]["valid"]:raise EngineeringError("QUANTITY_VALIDATION_FAILED","Derived quantities failed consistency validation",{"errors":out["validation"]["errors"]})
  out["quantity_hash"]=canonical_hash({"inputs":[out["input_world_model_hash"],out["input_design_hash"],out["input_geometry_hash"]],"source":out["measurement_provenance"]["geometry_source"],"engine":out["engine_version"],"config":self.config.canonical(),"quantities":quantities})
  return out

 def from_solids(self,world:dict,alternative:dict,geometry:dict)->dict:
  """Take quantities off the persisted B-rep instead of off a description of one.

  The distinction this method exists to keep is between a number that was measured
  on a solid and a number that was declared by the programme. Both end up in the
  same list, because a quantity surveyor needs both, but every item carries its
  ``type`` and its ``source`` so that nothing downstream can mistake a declared
  figure for a measured one. In particular the design engine's analytical volume
  is *not* used: where the kernel reports a different number, the kernel wins and
  the divergence is recorded rather than quietly reconciled.
  """
  solids=geometry["measurements"];metrics=alternative.get("metrics") or {}
  volume=geometry["combined_volume_m3"];area=geometry["combined_area_m2"];bbox=geometry.get("combined_bounding_box")
  provider=geometry.get("provider") or "unknown"
  if volume is None or area is None:
   raise EngineeringError("QUANTITY_SOURCE_INVALID","The persisted solid carries no measured totals",{"geometry_artifact_id":geometry.get("id")})
  if not bbox:
   raise EngineeringError("QUANTITY_SOURCE_INVALID","The persisted solid carries no bounding box, so its extents cannot be read",{"geometry_artifact_id":geometry.get("id")})
  x=float(bbox["max"][0])-float(bbox["min"][0]);y=float(bbox["max"][1])-float(bbox["min"][1]);z=float(bbox["max"][2])-float(bbox["min"][2])
  footprint=x*y;ratio=self.config.external_wall_uncertainty_ratio;wall=2*(x+y)*z
  gfa=metrics.get("gross_floor_area_m2");floors=metrics.get("floor_count");site_area=metrics.get("site_area_m2")
  core_per_floor=metrics.get("core_area_per_floor_m2");parking=metrics.get("parking_count")
  def total(key):return sum(int(s[key]) for s in solids)
  declared_basis="DesignAlternative.key_metrics_json"
  quantities=[
   item("BUILDING_VOLUME","Building Envelope Volume",volume,"m3","EXACT_MEASURED",f"volume of the B-rep solid(s) summed by {provider} over {len(solids)} solid(s)",3),
   item("ENVELOPE_SURFACE_AREA","Total Envelope Surface Area",area,"m2","EXACT_MEASURED",f"sum of every face of the solid(s) reported by {provider}: the roof plane, the base and the underside are all included. This is not a wall area and not a roof area.",3),
   item("FOOTPRINT","Building Footprint",footprint,"m2","EXACT_DERIVED","plan area of the axis-aligned bounding box of the measured solid",2),
   item("BUILDING_HEIGHT","Overall Building Height",z,"m","EXACT_DERIVED","z-extent of the axis-aligned bounding box of the measured solid",3),
   item("SOLID_COUNT","Solid Count",float(len(solids)),"count","EXACT_MEASURED",f"solids in the B-rep reported by {provider}",0),
   item("FACE_COUNT","B-rep Face Count",float(total("face_count")),"count","EXACT_MEASURED","faces of the B-rep reported by the kernel; topology only, not a set of building elements",0),
   item("EDGE_COUNT","B-rep Edge Count",float(total("edge_count")),"count","EXACT_MEASURED","edges of the B-rep reported by the kernel; topology only, not a set of building elements",0),
   item("VERTEX_COUNT","B-rep Vertex Count",float(total("vertex_count")),"count","EXACT_MEASURED","vertices of the B-rep reported by the kernel; topology only, not a set of building elements",0),
   item("GFA","Gross Floor Area",gfa,"m2","DECLARED_INPUT",f"{declared_basis}.gross_floor_area_m2. A programme figure declared for the design, not a measurement of the solid: gross floor area is a rateable area, and the kernel measures enclosed volume.",2),
   item("FLOOR_COUNT","Number of Floors",float(floors) if floors is not None else None,"count","DECLARED_INPUT",f"{declared_basis}.floor_count. Storeys are a programme statement; the B-rep has no storey subdivision to count.",0),
   item("SITE_AREA","Site Area",site_area,"m2","DECLARED_INPUT",f"{declared_basis}.site_area_m2. The site boundary is an input to the analysis, not a property of the building solid.",2),
   item("SITE_COVERAGE","Site Coverage",footprint/float(site_area) if site_area else None,"ratio","EXACT_DERIVED","measured footprint / declared site area",4),
   item("OPEN_SITE_AREA","Open Site Area",float(site_area)-footprint if site_area is not None else None,"m2","EXACT_DERIVED","declared site area - measured footprint",2),
   item("EXTERNAL_WALL_AREA","Approximate External Wall Area",wall,"m2","DERIVED_APPROXIMATION",f"bounding box perimeter x height. The measured total area cannot be split into wall, roof and base faces because the solid carries no semantic face labels; only {declared_basis} could say which face is which, and it does not.",2,{"lower_bound":round(wall*(1-ratio),2),"upper_bound":round(wall*(1+ratio),2),"basis":"configuration band around the bounding box perimeter; excludes openings and articulation","confidence":"LOW"}),
   item("CORE_AREA","Cumulative Conceptual Core Area",float(core_per_floor)*float(floors) if core_per_floor is not None and floors is not None else None,"m2","DERIVED_APPROXIMATION",f"{declared_basis}.core_area_per_floor_m2 x floor_count. The core is a programme diagram; it is not present in the solid."),
   item("PARKING_CAPACITY","Parking Capacity",parking,"count","DECLARED_INPUT" if parking is not None else "UNKNOWN",f"{declared_basis}.parking_count. A programme statement; no parking is modelled as geometry.",0),
   # The kernel reports total face area, not per-face area, and nothing in the
   # protocol labels a face as the roof. Reporting one would mean assuming the top
   # plane of the bounding box is a roof, which is the same fabrication this phase
   # exists to remove.
   item("ROOF_AREA","Roof Area",None,"m2","NOT_SUPPORTED","The B-rep reports total face area and no face is labelled as the roof, so the roof plane cannot be isolated without assuming the top of the bounding box is it."),
   item("CONCRETE_VOLUME","Concrete Volume",None,"m3","NOT_SUPPORTED","No member dimensions or slab specification"),
   item("REINFORCEMENT_MASS","Reinforcement Mass",None,"kg","NOT_SUPPORTED","No structural design")]
  out={"schema_version":"1.0.0","quantities":quantities,
   "assumptions":[{"code":"DECLARED_PROGRAMME_INPUTS","statement":"Gross floor area, floor count, site area, core area and parking are programme declarations carried from the design alternative. They are reported as declared, not as measured, and no solid measurement was substituted for them."},{"code":"SEMANTIC_FACES_ABSENT","statement":"The solid is a single massing body with no storeys, openings or labelled faces. Any quantity that would require the surface to be decomposed into such parts is an approximation or is not supported."}],
   "unknowns":[x["code"] for x in quantities if x["type"] in {"UNKNOWN","NOT_SUPPORTED"}],
   "uncertainty":{"classification":"PRELIMINARY","approximation_items":[x["code"] for x in quantities if x["type"] in {"DERIVED_APPROXIMATION","ASSUMPTION_BASED"}]},
   "measurement_provenance":{"geometry_source":"CAD_BREP","provider":provider,"geometry_engine_version":geometry.get("engine_version"),"cad_job_run_id":geometry.get("cad_job_run_id"),"geometry_artifact_id":geometry.get("id"),"geometry_hash":geometry["geometry_hash"],
    "measured_quantities":[x["code"] for x in quantities if x["type"]=="EXACT_MEASURED"],
    "derived_from_measurements":[x["code"] for x in quantities if x["type"]=="EXACT_DERIVED"],
    "declared_quantities":[x["code"] for x in quantities if x["type"]=="DECLARED_INPUT"],
    "approximated_quantities":[x["code"] for x in quantities if x["type"]=="DERIVED_APPROXIMATION"],
    "unsupported_quantities":[x["code"] for x in quantities if x["type"]=="NOT_SUPPORTED"],
    "notice":"Volumes, areas, extents and topology are read off the B-rep recorded by the CAD worker. Programme figures are declared, not measured, and are labelled as such on each item."},
   "input_world_model_hash":alternative["world_hash"],"input_design_hash":alternative["design_hash"],"input_geometry_hash":geometry["geometry_hash"],
   "engine_name":self.config.quantity_engine_name,"engine_version":self.config.quantity_engine_version,"config_version":self.config.config_version}
  out["validation"]=self.validator.validate_solids(out,geometry,{**alternative,"geometry_hash":geometry["geometry_hash"]})
  declared_volume=metrics.get("building_volume_m3")
  if declared_volume:
   d=float(declared_volume);drift=abs(volume-d)/abs(d) if d else None
   out["declared_vs_measured"]={"code":"DECLARED_VOLUME_DIVERGENCE","declared_source":f"{declared_basis}.building_volume_m3","declared_m3":round(d,6),"measured_m3":round(volume,6),"relative_difference":round(drift,6) if drift is not None else None,"authoritative":"measured","detail":"The design engine estimated the envelope volume arithmetically from its parameters. The kernel measured it on the solid. Where they differ the measured value is the one reported, and the declared value is kept here so the divergence stays visible instead of being reconciled away."}
  if not out["validation"]["valid"]:raise EngineeringError("QUANTITY_VALIDATION_FAILED","Measured quantities failed consistency validation",{"errors":out["validation"]["errors"],"geometry_artifact_id":geometry.get("id")})
  out["quantity_hash"]=canonical_hash({"inputs":[out["input_world_model_hash"],out["input_design_hash"],out["input_geometry_hash"]],"source":out["measurement_provenance"]["geometry_source"],"engine":out["engine_version"],"config":self.config.canonical(),"quantities":quantities})
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
 def calculate(self,world:dict,alternative:dict,geometry:dict,quantity:dict|None=None)->dict:
  facts=consumer_inputs(geometry,quantity)
  h=facts["height_m"];w=facts["width_m"];d=facts["depth_m"];floors=facts["floors"];grid=facts["grid"]
  # Classification is driven by whichever of storey count and height is known. Over a
  # solid the storey count is a programme declaration rather than a measurement, and
  # saying so is the point: a system classified off a declared storey count is a
  # weaker statement than one off a measured height, and the basis line records which.
  if h is None and floors is None:system="UNKNOWN"
  else:system="RC_FRAME_SHEAR_WALL" if (h is not None and h>35) or (floors is not None and floors>8) else "RC_FRAME"
  basis_parts=[]
  if floors is not None:basis_parts.append(f"{floors} {_origin(facts['floors_basis'])}")
  if h is not None:basis_parts.append(f"{h:.2f} m height, {_origin(facts['height_basis'])}")
  maxspan=max(float(grid["x_spacing"]),float(grid["y_spacing"])) if grid else None
  warnings=[{"code":"UNKNOWN_SOIL_CONDITIONS","message":"No verified geotechnical information is present; foundation concept remains unknown."}]
  if maxspan is None:
   # A measured solid carries no structural grid: it is a massing body, not a frame.
   # The distinction is recorded because a grid-less classification is a weaker
   # feasibility candidate, not a check on the frame that does not exist yet.
   warnings.append({"code":"STRUCTURAL_GRID_UNKNOWN","message":"No conceptual grid is available: the geometry carries no structural grid, so no span can be checked."})
  elif maxspan>self.config.long_span_m:warnings.append({"code":"LONG_SPAN","message":f"Conceptual grid span {maxspan:.2f} m exceeds the {self.config.long_span_m:.2f} m warning threshold."})
  if w and d and max(w/d,d/w)>self.config.high_aspect_ratio:warnings.append({"code":"HIGH_ASPECT_RATIO","message":"Persisted mass aspect ratio exceeds the configured conceptual threshold."})
  if h is not None and h>self.config.high_building_height_m:warnings.append({"code":"HIGH_BUILDING_HEIGHT","message":"Building height exceeds the configured conceptual threshold."})
  if floors is None:warnings.append({"code":"FLOOR_COUNT_UNKNOWN","message":"No storey count is available from the geometry or the programme, so the system is classified on height alone."})
  if h is None:warnings.append({"code":"BUILDING_HEIGHT_UNKNOWN","message":"No building height is available, so the system is classified on the declared storey count alone."})
  unknowns=["soil_conditions","loads","material_strengths","wind_and_seismic_actions","foundation_system"]+( ["lateral_system"] if system=="RC_FRAME" else [])+( ["structural_system"] if system=="UNKNOWN" else [])
  out={"schema_version":"1.0.0","structural_system":system,"system_basis":f"deterministic conceptual classification from {' and '.join(basis_parts) if basis_parts else 'no available inputs'}","grid":{"status":"CONCEPTUAL" if grid else "UNKNOWN","x_spacing_m":grid.get("x_spacing") if grid else None,"y_spacing_m":grid.get("y_spacing") if grid else None,"x_bays":grid.get("x_bays") if grid else None,"y_bays":grid.get("y_bays") if grid else None,"source":(facts["grid_basis"] or {}).get("source") if grid else None},"span_assumptions":{"maximum_conceptual_span_m":maxspan,"engineered":False},"vertical_system":"PRELIMINARY_FRAME_CANDIDATE" if system!="UNKNOWN" else "UNKNOWN","lateral_system":"PRELIMINARY_CORE_OR_SHEAR_WALL_CANDIDATE" if system=="RC_FRAME_SHEAR_WALL" else "UNKNOWN","foundation_concept":"UNKNOWN","assumptions":["Phase 2 grid is conceptual and not engineering approved.","System classification is a feasibility candidate only."],"warnings":warnings,"unknowns":unknowns,
   "input_basis":{"geometry_source":facts["geometry_source"],"quantity_hash":facts["quantity_hash"],"inputs":{k:v for k,v in {"plan_extents":facts["plan_basis"],"height":facts["height_basis"],"floor_count":facts["floors_basis"],"structural_grid":facts["grid_basis"]}.items() if v is not None}},
   "disclaimer":self.DISCLAIMER,"input_world_model_hash":alternative["world_hash"],"input_design_hash":alternative["design_hash"],"input_geometry_hash":geometry["geometry_hash"],"engine_name":self.config.structural_engine_name,"engine_version":self.config.structural_engine_version,"config_version":self.config.config_version}
  out["concept_hash"]=canonical_hash({"inputs":[out["input_world_model_hash"],out["input_design_hash"],out["input_geometry_hash"]],"engine":out["engine_version"],"config":self.config.canonical(),"concept":{k:out[k] for k in ["structural_system","grid","vertical_system","lateral_system","foundation_concept","warnings","unknowns","input_basis"]}})
  return out

#: Where a resolved consumer input came from, and what kind of number it is. The
#: distinction is carried rather than discarded because a conclusion drawn from a
#: declared height is a different claim from one drawn from a measured one, and the
#: reader cannot tell them apart from the conclusion alone.
MEASURED_EXTENT_BASIS={"basis":"GEOMETRY_MEASUREMENTS","type":"EXACT_MEASURED","source":"axis-aligned bounding box of the measured solid(s)"}
DESCRIBED_EXTENT_BASIS={"basis":"GEOMETRY_DESCRIPTION","type":"EXACT_DERIVED","source":"GeometryIR.mass dimensions"}
DESCRIBED_FLOOR_BASIS={"basis":"GEOMETRY_DESCRIPTION","type":"EXACT_DERIVED","source":"count(GeometryIR.floor_plates)"}
DESCRIBED_GRID_BASIS={"basis":"GEOMETRY_DESCRIPTION","type":"EXACT_DERIVED","source":"persisted GeometryIR preliminary grid"}

def consumer_inputs(geometry:dict,quantity:dict|None=None)->dict:
	"""Resolve the handful of dimensions the structural and regulatory consumers reason over.

	Both used to read the geometry description directly, which only works while every
	geometry artifact is a parametric description. Over a solid there is no mass, no
	floor plate and no structural grid to read, so the values come from the quantity
	artifact when there is one: that is where each value carries the label saying
	whether it was measured on a solid or declared by the programme. A structural
	conclusion drawn from a declared height has to be able to say that is what it drew
	from, and a regulatory verdict on a measured height is a stronger statement than
	one on a declared one.

	Every resolved value is returned next to where it came from. Callers with no
	quantity artifact to consult -- the engine unit tests, which exercise the
	engines directly -- fall back to the description, which is all that exists then.
	"""
	by={x["code"]:x for x in (quantity or {}).get("quantities",[])}
	def labelled(code):
		q=by.get(code)
		if q is None or q["value"] is None:return None,None
		return q["value"],{"basis":"QUANTITY_ARTIFACT","code":code,"type":q["type"],"source":q["source"],"quantity_hash":(quantity or {}).get("quantity_hash")}
	ir=geometry.get("geometry_ir");bbox=geometry.get("combined_bounding_box")
	width=depth=height=None;extent_basis=None
	if bbox:
		extents=[float(bbox["max"][i])-float(bbox["min"][i]) for i in range(3)]
		width,depth,height=extents[0],extents[1],extents[2];extent_basis=MEASURED_EXTENT_BASIS
	elif ir:
		mass=ir["masses"][0]["dimensions"]
		width,depth,height=float(mass["width"]),float(mass["depth"]),float(mass["height"]);extent_basis=DESCRIBED_EXTENT_BASIS
	labelled_height,height_basis=labelled("BUILDING_HEIGHT")
	if labelled_height is not None:height=float(labelled_height)
	elif height is not None:height_basis=extent_basis
	floors,floors_basis=labelled("FLOOR_COUNT")
	if floors is None and ir is not None:floors=float(len(ir["floor_plates"]));floors_basis=DESCRIBED_FLOOR_BASIS
	grid=None;grid_basis=None
	if ir is not None and ir.get("structural_grids"):
		grid=ir["structural_grids"][0]["dimensions"];grid_basis=DESCRIBED_GRID_BASIS
	provenance=(quantity or {}).get("measurement_provenance") or {}
	return {"width_m":width,"depth_m":depth,"height_m":height,"floors":None if floors is None else int(floors),
		"plan_basis":extent_basis,"height_basis":height_basis,"floors_basis":floors_basis,"grid":grid,"grid_basis":grid_basis,
		"geometry_source":provenance.get("geometry_source") or geometry.get("source"),
		"quantity_hash":(quantity or {}).get("quantity_hash")}

def _origin(basis:dict|None)->str:
	"""One phrase naming where an input came from, for use in a human-readable line."""
	if not basis:return "of unknown origin"
	kind={"GEOMETRY_MEASUREMENTS":"measured on the solid","GEOMETRY_DESCRIPTION":"read back from the geometry description"}.get(basis.get("basis"))
	if kind:return kind
	return {"EXACT_MEASURED":"measured on the solid","EXACT_DERIVED":"derived exactly","DECLARED_INPUT":"declared by the programme","DERIVED_APPROXIMATION":"approximated"}.get(basis.get("type"),"of unrecorded origin")

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
 def calculate(self,world:dict,alternative:dict,geometry:dict,quantity:dict|None=None)->dict:
  jurisdiction=world.get("site",{}).get("location",{}).get("country") or "UNKNOWN";ruleset=self.provider.get_ruleset(jurisdiction)
  metrics=alternative["metrics"];facts={**metrics,"building_use":world.get("building",{}).get("use"),"setback_m":alternative.get("parameters",{}).get("setback_m")}
  # A rule is evaluated against the best number available for the parameter it names.
  # Where the quantity artifact carries that parameter, its value is used over the
  # alternative's own metric: a height measured on the solid is a better answer to a
  # height limit than a height the design engine declared about itself. The metric is
  # kept as the fallback, and each fact records which one was used so that a verdict
  # can be traced to the number behind it rather than to the field it sat in.
  by={x["code"]:x for x in (quantity or {}).get("quantities",[])}
  origins={}
  for parameter,code in (("building_height_m","BUILDING_HEIGHT"),("site_coverage_ratio","SITE_COVERAGE"),("floor_count","FLOOR_COUNT"),("parking_count","PARKING_CAPACITY"),("gross_floor_area_m2","GFA")):
   if parameter in metrics:origins[parameter]={"basis":"ALTERNATIVE_METRIC","type":"DECLARED_INPUT","source":"DesignAlternative.key_metrics_json"}
   if code in by and by[code]["value"] is not None:
    facts[parameter]=by[code]["value"];origins[parameter]={"basis":"QUANTITY_ARTIFACT","code":code,"type":by[code]["type"],"source":by[code]["source"]}
  if alternative.get("parameters",{}).get("setback_m") is not None:origins["setback_m"]={"basis":"ALTERNATIVE_PARAMETER","type":"DECLARED_INPUT","source":"DesignAlternative.design_parameters_json.setback_m"}
  results=[]
  if ruleset.get("rules"):
   for r in ruleset["rules"]:
    applicability,status,observed,reason=self._eval(r,facts);results.append({"rule_code":r["code"],"title":r["title"],"applicability":applicability,"status":status,"observed":observed,"threshold":r.get("threshold"),"unit":r.get("unit"),"calculation":f"{r['parameter']} {r['operator']} {r.get('threshold')}","reason":reason,"observed_basis":origins.get(r["parameter"]),"provenance":{"ruleset_id":ruleset.get("id"),"ruleset_version":ruleset["version"],"jurisdiction":ruleset["jurisdiction"],"source_reference":r.get("source_reference"),"effective_date":r.get("effective_date")}})
  else:
   for code,title,param,unit in self.EXPECTED:results.append({"rule_code":code,"title":title,"applicability":"UNKNOWN","status":"UNKNOWN","observed":facts.get(param),"threshold":None,"unit":unit,"calculation":"NO_RULE_AVAILABLE","reason":"No verified applicable rule is configured; no compliance conclusion is made.","observed_basis":origins.get(param),"provenance":{"ruleset_id":None,"ruleset_version":ruleset["version"],"jurisdiction":jurisdiction,"source_reference":None,"effective_date":None}})
  counts={s:sum(x["status"]==s for x in results) for s in ["PASS","FAIL","UNKNOWN","NOT_APPLICABLE"]};overall="FAIL" if counts["FAIL"] else "UNKNOWN" if counts["UNKNOWN"] else "PASS"
  out={"schema_version":"1.0.0","jurisdiction":jurisdiction,"ruleset":{k:ruleset.get(k) for k in ["id","authority","version","effective_date","source_type","source_reference","authoritative"]},"results":results,"summary":counts,"overall_status":overall,
   "fact_provenance":origins,"geometry_source":(quantity or {}).get("measurement_provenance",{}).get("geometry_source") or geometry.get("source"),
   "notice":"This evaluation is preliminary and is not regulatory approval or a compliance certificate.","input_world_model_hash":alternative["world_hash"],"input_design_hash":alternative["design_hash"],"input_geometry_hash":geometry["geometry_hash"],"engine_name":self.config.regulatory_engine_name,"engine_version":self.config.regulatory_engine_version,"config_version":self.config.config_version}
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

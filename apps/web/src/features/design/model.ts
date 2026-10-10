export type Alternative={id:string;name:string;strategy_id:string;status:string;metrics:Record<string,number|null>;constraint_results:any[];reasoning:any;tradeoffs:any[];design_hash:string;geometry_hash:string;input_world_model_hash:string;design_engine_version:string;config_version:string;provenance:any;geometry_available:boolean};

export function metricRows(alternatives:Alternative[]){
 return ['gross_floor_area_m2','building_footprint_m2','site_coverage_ratio','floor_count','building_height_m','open_site_area_m2'].map(key=>({key,values:alternatives.map(a=>a.metrics[key])}));
}
export function statusLabel(status:string){return status==='STALE'?'STALE — generated from an older World Model':status;}

export type CadGeometryState="READY"|"MISSING"|"STALE"|"UNAVAILABLE";
export function cadGeometryState(url:string|null|undefined,status:string|null|undefined):CadGeometryState{
 if(status==="STALE")return "STALE";
 if(status && status!=="CURRENT")return "UNAVAILABLE";
 return url?"READY":"MISSING";
}

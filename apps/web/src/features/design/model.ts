export type GeometryIR={site:any;setbacks:any[];masses:any[];floor_plates:any[];cores:any[];structural_grids:any[];dimensions:any[];parking:any;orientation_degrees:number|null;metadata:any};
export type Alternative={id:string;name:string;strategy_id:string;status:string;metrics:Record<string,number|null>;constraint_results:any[];reasoning:any;tradeoffs:any[];design_hash:string;geometry_hash:string;input_world_model_hash:string;design_engine_version:string;config_version:string;provenance:any;geometry_available:boolean};

export function scenePlan(ir:GeometryIR|null){
 if(!ir)return {site:0,floors:0,cores:0,grids:0,dimensions:0,objects:0};
 const plan={site:ir.site?1:0,floors:ir.floor_plates.length,cores:ir.cores.length,grids:ir.structural_grids.length,dimensions:ir.dimensions.length,objects:0};
 plan.objects=plan.site+plan.floors+plan.cores+plan.grids+plan.dimensions+ir.masses.length+ir.setbacks.length;
 return plan;
}
export function metricRows(alternatives:Alternative[]){
 return ['gross_floor_area_m2','building_footprint_m2','site_coverage_ratio','floor_count','building_height_m','open_site_area_m2'].map(key=>({key,values:alternatives.map(a=>a.metrics[key])}));
}
export function statusLabel(status:string){return status==='STALE'?'STALE — generated from an older World Model':status;}

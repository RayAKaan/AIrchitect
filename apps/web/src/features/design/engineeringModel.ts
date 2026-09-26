export const regulatoryLabel=(status:string)=>status==='NOT_APPLICABLE'?'N/A':status;
export const isCurrent=(artifact:any)=>Boolean(artifact&&artifact.status==='CURRENT');
export function engineeringComparisonRow(data:any){return {gfa:data?.alternative?.metrics?.gross_floor_area_m2??null,quantityStatus:data?.quantity?.status??'NOT_CALCULATED',cost:data?.cost?.total_cost??null,costStatus:data?.cost?.status??'COST_UNAVAILABLE',structure:data?.structure?.structural_system??'NOT_CALCULATED',regulation:data?.regulatory?.overall_status??'NOT_CALCULATED'};}
export function uncertaintyVisible(quantity:any){return quantity?.type==='DERIVED_APPROXIMATION'&&quantity?.uncertainty?.lower_bound!=null&&quantity?.uncertainty?.upper_bound!=null;}

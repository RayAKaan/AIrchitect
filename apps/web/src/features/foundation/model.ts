export type FoundationSnapshot = {requirements:any[]; assumptions:any[]; world_model:any};

export function summarizeSnapshot(snapshot:FoundationSnapshot|null){
 return {confirmed:snapshot?.requirements.filter(r=>r.status==='CONFIRMED').length||0,
  assumed:snapshot?.assumptions.filter(a=>['proposed','accepted'].includes(a.status)).length||0,
  unknown:snapshot?.world_model?.unknowns?.length||0};
}

export function buildFloorCountChange(currentVersionId:string,revision:number,floors:number){
 if(!Number.isInteger(floors)||floors<1)throw new Error('Floor count must be a positive integer');
 return {expected_current_version_id:currentVersionId,expected_revision:revision,
  change_summary:`Change floor count to ${floors}`,changes:{floor_count:floors}};
}

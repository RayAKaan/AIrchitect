import { describe, expect, it } from 'vitest';
import { buildFloorCountChange, summarizeSnapshot } from './model';

describe('Phase 1 canonical UI model',()=>{
 it('summarizes confirmed, assumed and unknown state without treating unknown as zero',()=>{
  expect(summarizeSnapshot({requirements:[{status:'CONFIRMED'},{status:'EXTRACTED'}],assumptions:[{status:'proposed'}],world_model:{unknowns:['site.area','parking.arrangement']}}))
   .toEqual({confirmed:1,assumed:1,unknown:2});
 });
 it('builds an optimistic canonical version change',()=>{
  expect(buildFloorCountChange('v1',4,8)).toEqual({expected_current_version_id:'v1',expected_revision:4,change_summary:'Change floor count to 8',changes:{floor_count:8}});
 });
 it('rejects invalid floor counts',()=>expect(()=>buildFloorCountChange('v1',1,0)).toThrow());
});

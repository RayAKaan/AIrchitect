import {describe,expect,it} from 'vitest';
import {metricRows,scenePlan,statusLabel} from './model';
const ir:any={site:{},setbacks:[{}],masses:[{}],floor_plates:[{},{},{}],cores:[{}],structural_grids:[{}],dimensions:[{},{},{}],parking:{},orientation_degrees:null,metadata:{}};
describe('Phase 2 design view model',()=>{
 it('maps persisted Geometry IR into real scene object counts',()=>expect(scenePlan(ir)).toEqual({site:1,floors:3,cores:1,grids:1,dimensions:3,objects:11}));
 it('builds metric comparison without choosing a best design',()=>{const rows=metricRows([{metrics:{gross_floor_area_m2:8000}} as any,{metrics:{gross_floor_area_m2:7800}} as any]);expect(rows[0].values).toEqual([8000,7800])});
 it('communicates stale status in words, not color alone',()=>expect(statusLabel('STALE')).toContain('older World Model'));
});

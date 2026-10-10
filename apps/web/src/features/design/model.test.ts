import {describe,expect,it} from 'vitest';
import {cadGeometryState,metricRows,statusLabel} from './model';

describe('Phase 19 CAD-authoritative design view model',()=>{
 it('requires a real GLB before reporting geometry ready',()=>{
  expect(cadGeometryState(null,'CURRENT')).toBe('MISSING');
  expect(cadGeometryState(undefined,null)).toBe('MISSING');
  expect(cadGeometryState('/artifact.glb','CURRENT')).toBe('READY');
 });
 it('never presents stale geometry as current',()=>{
  expect(cadGeometryState('/artifact.glb','STALE')).toBe('STALE');
  expect(cadGeometryState(null,'STALE')).toBe('STALE');
 });
 it('does not mark failed or unknown artifact states ready',()=>{
  expect(cadGeometryState('/artifact.glb','FAILED')).toBe('UNAVAILABLE');
 });
 it('builds metric comparison without choosing a best design',()=>{
  const rows=metricRows([{metrics:{gross_floor_area_m2:8000}} as any,{metrics:{gross_floor_area_m2:7800}} as any]);
  expect(rows[0].values).toEqual([8000,7800]);
 });
 it('communicates stale status in words, not color alone',()=>expect(statusLabel('STALE')).toContain('older World Model'));
});

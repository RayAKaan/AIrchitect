import { Suspense, useEffect, useMemo, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { Bounds, Grid, Html, OrbitControls, useBounds } from '@react-three/drei';
import * as THREE from 'three';
import { emitWorkspaceSelection, WORKSPACE_SELECTION_EVENT, type WorkspaceSelectionEvent } from './features/foundation/workspaceEvents';
import { FloorPlanCanvas } from './features/scene/FloorPlanCanvas';
import './GeometryViewer.css';

type Artifact = { id:string; type:string; status:string; alternative_id:string|null; hash:string; payload:any };
type Snapshot = { version:{number:number}; artifacts:Artifact[]; world_model:any };

function FitButton(){ const bounds=useBounds(); return <Html fullscreen><button onClick={()=>bounds.refresh().fit()} className="fit-button">Fit to view</button></Html> }
function Massing({artifact,showFloors}:{artifact:Artifact;showFloors:boolean}){
 const p=artifact.payload; const vertices=p.vertices as [number,number,number][];
 const width=Math.max(...vertices.map(v=>v[0]))-Math.min(...vertices.map(v=>v[0]));
 const depth=Math.max(...vertices.map(v=>v[1]))-Math.min(...vertices.map(v=>v[1]));
 const height=p.height_m as number; const floors=Math.max(1,Math.round(p.gross_floor_area_m2/p.footprint_area_m2));
 return <group position={[0,height/2,0]}>
  <mesh castShadow receiveShadow><boxGeometry args={[width,height,depth]}/><meshStandardMaterial color="#b97847" roughness={0.72} metalness={0.04}/></mesh>
  <lineSegments><edgesGeometry args={[new THREE.BoxGeometry(width,height,depth)]}/><lineBasicMaterial color="#5b3624"/></lineSegments>
  {showFloors&&Array.from({length:floors-1},(_,i)=>{const y=-height/2+(height/floors)*(i+1);return <mesh key={i} position={[0,y,depth/2+.015]}><planeGeometry args={[width,.025]}/><meshBasicMaterial color="#fff3e8"/></mesh>})}
  <Html position={[width/2+.4,0,depth/2]}><span className="dimension-label">{height.toFixed(1)} m</span></Html>
 </group>
}

/** Actual WebGL 3D viewer. Geometry comes only from persisted canonical geometry artifacts. */
export default function GeometryViewer({api,token,projectId,onClose}:{api:string;token:string;projectId:string;onClose:()=>void}){
 const [snapshot,setSnapshot]=useState<Snapshot|null>(null); const [selected,setSelected]=useState('');
 const [showFloors,setShowFloors]=useState(true); const [busy,setBusy]=useState(true); const [error,setError]=useState('');
 const [viewMode,setViewMode]=useState<'3d'|'2d'>('3d');
 const [selectedLevel,setSelectedLevel]=useState(1);
 const [selectedSpaceId,setSelectedSpaceId]=useState<string|null>(null);
 useEffect(()=>{(async()=>{setBusy(true);setError('');try{
  const headers={Authorization:`Bearer ${token}`}; const vr=await fetch(`${api}/projects/${projectId}/versions`,{headers}); if(!vr.ok)throw Error('Could not load project versions');
  const versions=await vr.json(); if(!versions.length)throw Error('No project version exists'); const sr=await fetch(`${api}/projects/${projectId}/versions/${versions[0].version}/snapshot`,{headers});
  if(!sr.ok)throw Error('Could not load canonical project snapshot'); const data=await sr.json(); setSnapshot(data);
  const first=data.artifacts.find((a:Artifact)=>a.type==='geometry'&&a.status!=='stale'); setSelected(first?.id||'');
 }catch(e){setError(e instanceof Error?e.message:'Viewer failed')}finally{setBusy(false)}})()},[api,token,projectId]);
 const spatialLayouts=useMemo(()=>snapshot?.artifacts.filter(a=>a.type==='spatial_layout'&&a.status!=='stale')||[],[snapshot]);
 const spatialLayout=spatialLayouts.find(a=>a.alternative_id===artifact?.alternative_id)||spatialLayouts[0];
 const levels=useMemo(()=>{
  const values=(spatialLayout?.payload?.spaces||[]).map((space:any)=>space.level_number).filter((value:any)=>Number.isInteger(value));
  return [...new Set<number>(values)].sort((a,b)=>a-b);
 },[spatialLayout]);
 useEffect(()=>{
  if(levels.length&&!levels.includes(selectedLevel)) setSelectedLevel(levels[0]);
  if(!levels.length) setSelectedSpaceId(null);
 },[levels,selectedLevel]);
 useEffect(()=>{
  if(!selected) return;
  emitWorkspaceSelection({artifactId:selected,projectId,elementId:selectedSpaceId||undefined});
 },[selected,selectedSpaceId,projectId]);
 useEffect(()=>{
  const onSelection=(event:Event)=>{
    const detail=(event as CustomEvent<WorkspaceSelectionEvent>).detail;
    if(detail?.projectId===projectId){
      if(detail.artifactId!==selected) setSelected(detail.artifactId);
      if(detail.elementId!==undefined&&detail.elementId!==selectedSpaceId) setSelectedSpaceId(detail.elementId);
    }
  };
  window.addEventListener(WORKSPACE_SELECTION_EVENT,onSelection);
  return()=>window.removeEventListener(WORKSPACE_SELECTION_EVENT,onSelection);
 },[projectId,selected,selectedSpaceId]);
 const geometries=useMemo(()=>snapshot?.artifacts.filter(a=>a.type==='geometry')||[],[snapshot]);
 const artifact=geometries.find(a=>a.id===selected)||geometries[0];
 return <section className="viewer-shell"><div className="viewer-head"><div><p className="eyebrow">PERSISTED GEOMETRY</p><h2>3D massing</h2><small>WebGL · project version {snapshot?.version.number??'—'} · canonical artifacts only</small></div><button className="btn outline" onClick={onClose}>Close</button></div>
 {busy&&<div className="empty-state"><div className="spinner"/>Loading persisted geometry…</div>}
 {error&&<div className="alert">{error}</div>}
 {!busy&&!error&&!artifact&&<div className="empty-state"><h3>No geometry artifact</h3><p>Submit a complete brief and run the feasibility workflow first.</p></div>}
 {artifact&&<div className="viewer-layout">
 <div className="viewer-main">
  <div className="viewer-mode-switch" role="group" aria-label="View mode">
   <button type="button" className={viewMode==='2d'?'active':''} aria-pressed={viewMode==='2d'} disabled={!spatialLayout} onClick={()=>setViewMode('2d')}>2D floor plan</button>
   <button type="button" className={viewMode==='3d'?'active':''} aria-pressed={viewMode==='3d'} onClick={()=>setViewMode('3d')}>3D massing</button>
  </div>
  {viewMode==='3d'&&<div className="canvas-wrap three-canvas"><Canvas shadows camera={{position:[45,35,45],fov:42}}><color attach="background" args={['#eeece5']}/><ambientLight intensity={1.5}/><directionalLight castShadow position={[30,45,20]} intensity={2}/><Suspense fallback={null}><Bounds fit clip observe margin={1.25}><Massing artifact={artifact} showFloors={showFloors}/><FitButton/></Bounds></Suspense><Grid infiniteGrid fadeDistance={150} sectionColor="#9a765f" cellColor="#c9c2b8"/><OrbitControls makeDefault enablePan enableZoom enableRotate/></Canvas></div>}
  {viewMode==='2d'&&spatialLayout&&<div className="floorplan-panel">
   <label className="floorplan-level">Floor level<select value={selectedLevel} onChange={event=>setSelectedLevel(Number(event.target.value))}>{levels.map(level=><option key={level} value={level}>Level {level}</option>)}</select></label>
   <FloorPlanCanvas layout={spatialLayout.payload} level={selectedLevel} selectedSpaceId={selectedSpaceId} onSelect={space=>setSelectedSpaceId(space.id)}/>
   <p className="floorplan-source">Derived from persisted spatial layout · {spatialLayout.hash}</p>
  </div>}
 </div>
 <aside className="artifact-panel"><h3>Alternatives</h3>{geometries.map((a,i)=><button className={`alt-btn ${a.id===artifact.id?'active':''}`} key={a.id} onClick={()=>setSelected(a.id)}>Alternative {i+1}<small>{a.status} · {a.payload.height_m.toFixed(1)} m</small></button>)}{viewMode==='3d'&&<label className="toggle"><input type="checkbox" checked={showFloors} onChange={e=>setShowFloors(e.target.checked)}/> Floor visibility</label>}{viewMode==='2d'&&selectedSpaceId&&<><h3>Selected space</h3><p>{spatialLayout?.payload?.spaces?.find((space:any)=>space.id===selectedSpaceId)?.name||selectedSpaceId}</p></>}<h3>Artifact lineage</h3><dl><dt>Artifact version</dt><dd>{artifact.id}</dd><dt>Geometry SHA-256</dt><dd className="hash">{artifact.payload.geometry_sha256}</dd><dt>Gross floor area</dt><dd>{artifact.payload.gross_floor_area_m2.toLocaleString()} m²</dd><dt>Status</dt><dd>{artifact.status}</dd></dl></aside></div>}
 <div className="caveats"><b>Preliminary geometry only</b><p>Orbit, pan and zoom are enabled. This massing is not BIM, regulatory approval, or engineering certification.</p></div></section>
}

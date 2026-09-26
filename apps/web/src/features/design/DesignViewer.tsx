import {useEffect,useMemo,useRef,useState} from 'react';
import {Canvas,useThree} from '@react-three/fiber';
import {Edges,Html,OrbitControls} from '@react-three/drei';
import type {OrbitControls as OrbitControlsImpl} from 'three-stdlib';
import * as THREE from 'three';
import type {GeometryIR} from './model';

type Mode='solid'|'wireframe'|'ghost'; type Preset='iso'|'top'|'front'|'rear'|'left'|'right';
export default function DesignViewer({ir,geometryHash}:{ir:GeometryIR;geometryHash:string}){
 const floors=ir.floor_plates.map(x=>x.metadata.level_number as number);const maxHeight=Math.max(...ir.masses.map(x=>x.dimensions.height),1);
 const [floor,setFloor]=useState<number|0>(0);const [mode,setMode]=useState<Mode>('solid');const [grid,setGrid]=useState(true);
 const [preset,setPreset]=useState<Preset>('iso');const [fit,setFit]=useState(0);const [clip,setClip]=useState(maxHeight);const [section,setSection]=useState(false);
 useEffect(()=>{setFloor(0);setClip(maxHeight);setFit(x=>x+1)},[geometryHash,maxHeight]);
 return <div className="design-viewer"><div className="viewer-toolbar" aria-label="3D viewer controls">
  <button onClick={()=>setFit(x=>x+1)}>Fit view</button><button onClick={()=>{setPreset('iso');setFit(x=>x+1)}}>Reset</button>
  {(['iso','top','front','rear','left','right'] as Preset[]).map(x=><button aria-pressed={preset===x} onClick={()=>setPreset(x)} key={x}>{x}</button>)}
  <select aria-label="Render mode" value={mode} onChange={e=>setMode(e.target.value as Mode)}><option value="solid">Solid</option><option value="wireframe">Wireframe</option><option value="ghost">Ghost</option></select>
  <select aria-label="Floor visibility" value={floor} onChange={e=>setFloor(+e.target.value)}><option value={0}>All floors</option>{floors.map(n=><option key={n} value={n}>Isolate floor {n}</option>)}</select>
  <label><input type="checkbox" checked={grid} onChange={e=>setGrid(e.target.checked)}/> Grid</label><label><input type="checkbox" checked={section} onChange={e=>setSection(e.target.checked)}/> Section</label>
 </div>{section&&<label className="section-slider">Section height <input type="range" min="0" max={maxHeight} step=".1" value={clip} onChange={e=>setClip(+e.target.value)}/><output>{clip.toFixed(1)} m</output></label>}
 <div className="viewer-canvas" role="img" aria-label={`Interactive persisted building geometry ${geometryHash.slice(0,12)}`}><Canvas shadows camera={{fov:42,near:.1,far:5000}} onCreated={({gl})=>{gl.localClippingEnabled=true}}>
  <color attach="background" args={['#171a1d']}/><ambientLight intensity={1.2}/><directionalLight position={[60,90,40]} intensity={2.4} castShadow/>
  <Scene ir={ir} floor={floor} mode={mode} showGrid={grid} section={section} clipHeight={clip}/>
  <CameraRig ir={ir} preset={preset} fitSignal={fit}/>
 </Canvas></div><div className="viewer-foot"><span>Orbit: drag · Pan: right-drag · Zoom: wheel</span><code>{geometryHash}</code></div></div>
}
function CameraRig({ir,preset,fitSignal}:{ir:GeometryIR;preset:Preset;fitSignal:number}){
 const {camera}=useThree();const controls=useRef<OrbitControlsImpl>(null);const site=ir.site.dimensions;const h=Math.max(...ir.masses.map(x=>x.dimensions.height),1);
 useEffect(()=>{const cx=site.width/2,cz=site.depth/2,size=Math.max(site.width,site.depth,h)*1.45;const positions:Record<Preset,[number,number,number]>={iso:[cx+size,size,cz+size],top:[cx,size*1.5,cz+.01],front:[cx,h/2,cz+size],rear:[cx,h/2,cz-size],left:[cx-size,h/2,cz],right:[cx+size,h/2,cz]};camera.position.set(...positions[preset]);camera.up.set(0,1,0);controls.current?.target.set(cx,h/2,cz);controls.current?.update()},[preset,fitSignal,ir,camera,site.width,site.depth,h]);
 return <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={.08} enablePan enableRotate enableZoom/>;
}
function Scene({ir,floor,mode,showGrid,section,clipHeight}:{ir:GeometryIR;floor:number;mode:Mode;showGrid:boolean;section:boolean;clipHeight:number}){
 const clip=useMemo(()=>new THREE.Plane(new THREE.Vector3(0,-1,0),clipHeight),[clipHeight]);const clips=section?[clip]:[];const opacity=mode==='ghost'?.22:1;
 const site=ir.site.dimensions;
 return <group><mesh position={[site.width/2,-.08,site.depth/2]} receiveShadow><boxGeometry args={[site.width,.15,site.depth]}/><meshStandardMaterial color="#343b3a" roughness={1}/><Edges color="#8aa09a"/></mesh>
  {ir.setbacks.map(x=><Boundary key={x.id} obj={x} color="#c98950"/>)}
  {ir.floor_plates.filter(x=>floor===0||x.metadata.level_number===floor).map((x,index)=>{const t=x.transform.translation,d=x.dimensions;return <mesh key={x.id} position={[t[0]+d.width/2,t[2]+d.thickness/2,t[1]+d.depth/2]} castShadow receiveShadow>
   <boxGeometry args={[d.width,d.thickness,d.depth]}/><meshStandardMaterial color={index%2?'#b86f45':'#cf8b5d'} wireframe={mode==='wireframe'} transparent={mode==='ghost'} opacity={opacity} clippingPlanes={clips}/><Edges color="#f1c8a8"/></mesh>})}
  {ir.cores.map(x=>{const t=x.transform.translation,d=x.dimensions;return <mesh key={x.id} position={[t[0]+d.width/2,d.height/2,t[1]+d.depth/2]} castShadow><boxGeometry args={[d.width,d.height,d.depth]}/><meshStandardMaterial color="#687a7e" transparent opacity={mode==='ghost'?.12:.72} wireframe={mode==='wireframe'} clippingPlanes={clips}/></mesh>})}
  {showGrid&&ir.structural_grids.map(x=><GridLines key={x.id} obj={x}/>) }
  {ir.dimensions.map((x,i)=><Dimension key={x.id} obj={x} mass={ir.masses[0]} index={i}/>)}
  {ir.orientation_degrees!=null&&<Html position={[site.width-2,.5,2]}><div className="north-label" style={{transform:`rotate(${ir.orientation_degrees}deg)`}}>N ↑</div></Html>}
 </group>;
}
function Boundary({obj,color}:{obj:any;color:string}){const t=obj.transform.translation,d=obj.dimensions;return <mesh position={[t[0]+d.width/2,.02,t[1]+d.depth/2]}><boxGeometry args={[d.width,.02,d.depth]}/><meshBasicMaterial transparent opacity={0}/><Edges color={color}/></mesh>}
function GridLines({obj}:{obj:any}){const t=obj.transform.translation,d=obj.dimensions;const xs=Array.from({length:d.x_bays+1},(_,i)=>i*d.x_spacing);const ys=Array.from({length:d.y_bays+1},(_,i)=>i*d.y_spacing);return <group position={[t[0],.05,t[1]]}>{xs.map((x:number,i:number)=><mesh key={`x${i}`} position={[x,0,d.depth/2]}><boxGeometry args={[.025,.025,d.depth]}/><meshBasicMaterial color="#678d91"/></mesh>)}{ys.map((z:number,i:number)=><mesh key={`y${i}`} position={[d.width/2,0,z]}><boxGeometry args={[d.width,.025,.025]}/><meshBasicMaterial color="#678d91"/></mesh>)}</group>}
function Dimension({obj,mass,index}:{obj:any;mass:any;index:number}){const t=mass.transform.translation,d=mass.dimensions;const positions:[[number,number,number],[number,number,number],[number,number,number]]=[[t[0]+d.width/2,.5,t[1]-.8],[t[0]-.8,.5,t[1]+d.depth/2],[t[0]+d.width+.7,d.height/2,t[1]+d.depth]];return <Html position={positions[index]||positions[0]} center><span className="geometry-dimension">{obj.metadata.label}</span></Html>}

import {Suspense,useEffect,useMemo,useRef,useState} from 'react';
import {Canvas,useThree} from '@react-three/fiber';
import {Html,OrbitControls,useGLTF} from '@react-three/drei';
import type {OrbitControls as OrbitControlsImpl} from 'three-stdlib';
import * as THREE from 'three';

export default function DesignViewer({geometryHash,cadGlbUrl,geometryStatus,errorMessage}:{geometryHash:string;cadGlbUrl?:string|null;geometryStatus?:string|null;errorMessage?:string|null}){
  const [fitSignal,setFitSignal]=useState(0);
  const stale=geometryStatus==='STALE';
  return <div className="design-viewer">
    <div className="viewer-toolbar" aria-label="3D viewer controls">
      <span className={stale?'design-warning':'cad-badge'}>{stale?'STALE CAD ARTIFACT':'AUTHORITATIVE CAD / BIM'}</span>
      <button onClick={()=>setFitSignal(x=>x+1)} disabled={!cadGlbUrl}>Fit view</button>
    </div>
    {cadGlbUrl?<div className="viewer-canvas" role="img" aria-label={`Interactive persisted CAD geometry ${geometryHash.slice(0,12)}`}>
      <Canvas shadows camera={{fov:42,near:.01,far:100000}} onCreated={({gl})=>{gl.localClippingEnabled=true}}>
        <color attach="background" args={['#171a1d']}/>
        <ambientLight intensity={1.2}/>
        <directionalLight position={[60,90,40]} intensity={2.4} castShadow/>
        <Suspense fallback={<Html center><div className="design-state">Loading CAD model…</div></Html>}>
          <CadScene url={cadGlbUrl} fitSignal={fitSignal}/>
        </Suspense>
        <gridHelper args={[100,100,'#45504e','#303735']}/>
      </Canvas>
    </div>:<div className="design-state" role="status">
      <b>{stale?'CAD geometry is stale':geometryStatus==='FAILED'?'CAD generation failed':'No authoritative CAD model available'}</b>
      <span>{errorMessage||'Generate a CAD/BIM model for this alternative to view real geometry. AIrchitect does not substitute a fabricated preview for missing CAD output.'}</span>
    </div>}
    <div className="viewer-foot"><span>Orbit: drag · Pan: right-drag · Zoom: wheel</span><code>{geometryHash||'No CAD artifact hash'}</code></div>
  </div>;
}

function CadScene({url,fitSignal}:{url:string;fitSignal:number}){
  const {scene}=useGLTF(url);
  const object=useMemo(()=>scene.clone(true),[scene]);
  const {camera}=useThree();
  const controls=useRef<OrbitControlsImpl>(null);
  useEffect(()=>{
    const box=new THREE.Box3().setFromObject(object);
    if(box.isEmpty())return;
    const center=box.getCenter(new THREE.Vector3());
    const size=box.getSize(new THREE.Vector3());
    const distance=Math.max(size.x,size.y,size.z,1)*1.8;
    camera.position.set(center.x+distance,center.y+distance*.75,center.z+distance);
    camera.near=Math.max(.01,distance/10000);
    camera.far=Math.max(1000,distance*100);
    camera.updateProjectionMatrix();
    controls.current?.target.copy(center);
    controls.current?.update();
  },[object,camera,fitSignal]);
  return <>
    <primitive object={object}/>
    <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={.08} enablePan enableRotate enableZoom/>
  </>;
}

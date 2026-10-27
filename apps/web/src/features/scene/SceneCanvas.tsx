import { Canvas } from '@react-three/fiber';
import { Bounds, Grid, OrbitControls } from '@react-three/drei';
import { useMemo } from 'react';
import * as THREE from 'three';
import type { SceneMesh, ModelScene, SceneNode } from './sceneContract';

type SceneCanvasProps = Readonly<{ scene: ModelScene; selectedNodeId?: string | null; onSelect?: (node: SceneNode) => void }>;

function MeshGeometry({ mesh }: { mesh: SceneMesh }) {
  const geometry = useMemo(() => {
    const value = new Float32Array(mesh.vertices.flatMap((point) => point));
    const indices = mesh.faces.flatMap((face) => face.length >= 3 ? face.slice(1, -1).flatMap((_, index) => [face[0], face[index + 1], face[index + 2]]) : []);
    const result = new THREE.BufferGeometry();
    result.setAttribute('position', new THREE.BufferAttribute(value, 3));
    result.setIndex(indices);
    result.computeVertexNormals();
    return result;
  }, [mesh]);
  return <primitive object={geometry} dispose={null} />;
}

function NodeMesh({ node, mesh, selected, onSelect }: { node: SceneNode; mesh: SceneMesh; selected: boolean; onSelect?: (node: SceneNode) => void }) {
  return <mesh onClick={(event) => { event.stopPropagation(); onSelect?.(node); }}><MeshGeometry mesh={mesh} /><meshStandardMaterial color={selected ? '#b97847' : '#8b8177'} roughness={0.82} metalness={0.02} side={THREE.DoubleSide} /></mesh>;
}

export function SceneCanvas({ scene, selectedNodeId = null, onSelect }: SceneCanvasProps) {
  const center = useMemo<[number, number, number]>(() => [
    (scene.bounds.minimum[0] + scene.bounds.maximum[0]) / 2,
    (scene.bounds.minimum[1] + scene.bounds.maximum[1]) / 2,
    (scene.bounds.minimum[2] + scene.bounds.maximum[2]) / 2,
  ], [scene.bounds]);
  return <Canvas camera={{ position: [18, 14, 18], fov: 42 }}><color attach="background" args={['#eeece5']} /><ambientLight intensity={1.5} /><directionalLight position={[20, 30, 15]} intensity={2} /><Bounds fit clip observe margin={1.25}><group position={[-center[0], -center[1], -center[2]]}>{scene.nodes.map((node) => { const mesh = scene.meshes[node.meshIndex]; return mesh ? <NodeMesh key={node.id} node={node} mesh={mesh} selected={node.id === selectedNodeId} onSelect={onSelect} /> : null; })}</group></Bounds><Grid infiniteGrid fadeDistance={100} sectionColor="#9a765f" cellColor="#c9c2b8" /><OrbitControls makeDefault enablePan enableZoom enableRotate /></Canvas>;
}

import { useState } from 'react';
import type { ModelScene, SceneNode } from './sceneContract';
import { SceneCanvas } from './SceneCanvas';
import { SceneInspector } from './SceneInspector';

type SceneWorkspaceProps = Readonly<{
  scene: ModelScene;
}>;

export function SceneWorkspace({ scene }: SceneWorkspaceProps) {
  const [selectedNode, setSelectedNode] = useState<SceneNode | null>(null);
  return (
    <section className="viewer-shell" aria-label="3D model workspace">
      <div className="viewer-head">
        <div><p className="eyebrow">CANONICAL 3D WORKSPACE</p><h2>Model inspection</h2><small>Revision-independent presentation over canonical scene identity</small></div>
        {selectedNode && <button className="btn outline" onClick={() => setSelectedNode(null)}>Clear selection</button>}
      </div>
      <div className="viewer-layout">
        <div className="canvas-wrap three-canvas"><SceneCanvas scene={scene} selectedNodeId={selectedNode?.id ?? null} onSelect={setSelectedNode} /></div>
        <SceneInspector node={selectedNode} onClear={() => setSelectedNode(null)} />
      </div>
    </section>
  );
}

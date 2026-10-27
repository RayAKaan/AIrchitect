import { useState } from 'react';
import type { ModelScene, SceneNode } from './sceneContract';
import { EditToolbar, type EditCommand } from './EditToolbar';
import { SceneCanvas } from './SceneCanvas';
import { SceneInspector } from './SceneInspector';

type SceneWorkspaceProps = Readonly<{
  scene: ModelScene;
  onPreviewEdit?: (command: EditCommand) => void;
  onCommitEdit?: (command: EditCommand) => void;
}>;

export function SceneWorkspace({ scene, onPreviewEdit, onCommitEdit }: SceneWorkspaceProps) {
  const [selectedNode, setSelectedNode] = useState<SceneNode | null>(null);
  const previewEdit = onPreviewEdit ?? (() => undefined);
  const commitEdit = onCommitEdit ?? (() => undefined);

  return (
    <section className="viewer-shell" aria-label="3D model workspace">
      <div className="viewer-head">
        <div><p className="eyebrow">CANONICAL 3D WORKSPACE</p><h2>Model editing</h2><small>Edits are emitted as deterministic commands; persistence remains server-authoritative.</small></div>
        {selectedNode && <button className="btn outline" onClick={() => setSelectedNode(null)}>Clear selection</button>}
      </div>
      <EditToolbar elementId={selectedNode?.id ?? null} onPreview={previewEdit} onCommit={commitEdit} />
      <div className="viewer-layout">
        <div className="canvas-wrap three-canvas"><SceneCanvas scene={scene} selectedNodeId={selectedNode?.id ?? null} onSelect={setSelectedNode} /></div>
        <SceneInspector node={selectedNode} onClear={() => setSelectedNode(null)} />
      </div>
    </section>
  );
}

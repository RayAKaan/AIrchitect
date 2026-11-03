import { useState } from 'react';
import type { ModelScene, SceneNode, SceneView } from './sceneContract';
import { EditToolbar, type EditCommand } from './EditToolbar';
import { SceneCanvas } from './SceneCanvas';
import { SceneInspector } from './SceneInspector';
import { OrthographicSceneView } from './OrthographicSceneView';

type WorkspaceView = SceneView | '3d';

type SceneWorkspaceProps = Readonly<{
  scene: ModelScene;
  onPreviewEdit?: (command: EditCommand) => void;
  onCommitEdit?: (command: EditCommand) => void;
}>;

export function SceneWorkspace({ scene, onPreviewEdit, onCommitEdit }: SceneWorkspaceProps) {
  const [selectedNode, setSelectedNode] = useState<SceneNode | null>(null);
  const [view, setView] = useState<WorkspaceView>('plan');
  const previewEdit = onPreviewEdit ?? (() => undefined);
  const commitEdit = onCommitEdit ?? (() => undefined);

  return (
    <section className="viewer-shell" aria-label="Architectural model workspace">
      <div className="viewer-head">
        <div><p className="eyebrow">CANONICAL MODEL WORKSPACE</p><h2>Model editing</h2><small>Edits are emitted as deterministic commands; persistence remains server-authoritative.</small></div>
        {selectedNode && <button className="btn outline" onClick={() => setSelectedNode(null)}>Clear selection</button>}
      </div>
      <div className="edit-toolbar" role="group" aria-label="Architectural view selection">
        {(['plan', 'front', 'side'] as const).map(item => (
          <button key={item} type="button" className="btn outline" aria-pressed={view === item}
            onClick={() => setView(item)}>{item === 'plan' ? 'Plan' : item === 'front' ? 'Front elevation / section' : 'Side elevation / section'}</button>
        ))}
        <button type="button" className="btn outline" aria-pressed={view === '3d'}
          onClick={() => setView('3d')}>3D</button>
      </div>
      <EditToolbar elementId={selectedNode?.id ?? null} onPreview={previewEdit} onCommit={commitEdit} />
      <div className="viewer-layout">
        <div className={view === '3d' ? 'canvas-wrap three-canvas' : 'canvas-wrap orthographic-canvas'}>
          {view === '3d'
            ? <SceneCanvas scene={scene} selectedNodeId={selectedNode?.id ?? null} onSelect={setSelectedNode} />
            : <OrthographicSceneView scene={scene} view={view} selectedNodeId={selectedNode?.id ?? null} onSelect={setSelectedNode} />}
        </div>
        <SceneInspector node={selectedNode} onClear={() => setSelectedNode(null)} />
      </div>
    </section>
  );
}

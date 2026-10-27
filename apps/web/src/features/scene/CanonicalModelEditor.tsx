import { useState } from 'react';
import type { ApiClient } from '../../adapters/api/client';
import { commitCanonicalEdit, fetchCanonicalScene, previewCanonicalEdit } from '../../adapters/api/canonicalModel';
import { EditToolbar, type EditCommand } from './EditToolbar';
import { SceneCanvas } from './SceneCanvas';
import { SceneInspector } from './SceneInspector';
import type { ModelScene, SceneNode } from './sceneContract';

type CanonicalModelEditorProps = Readonly<{
  api: ApiClient;
  projectId: string;
  initialRevision: number;
  initialScene: ModelScene;
}>;

export function CanonicalModelEditor({ api, projectId, initialRevision, initialScene }: CanonicalModelEditorProps) {
  const [revision, setRevision] = useState(initialRevision);
  const [scene, setScene] = useState(initialScene);
  const [selectedNode, setSelectedNode] = useState<SceneNode | null>(null);
  const [message, setMessage] = useState<string>('');
  const [busy, setBusy] = useState(false);

  const preview = async (command: EditCommand) => {
    setBusy(true);
    setMessage('');
    try {
      const result = await previewCanonicalEdit(api, projectId, revision, [command]);
      setMessage(`Preview ready: revision ${result.result_revision}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Edit preview failed');
    } finally {
      setBusy(false);
    }
  };

  const commit = async (command: EditCommand) => {
    setBusy(true);
    setMessage('');
    try {
      const result = await commitCanonicalEdit(api, projectId, revision, [command]);
      const nextScene = await fetchCanonicalScene(api, projectId);
      setRevision(nextScene.revision);
      setScene(nextScene.scene);
      setSelectedNode(null);
      setMessage(`Saved revision ${result.model.revision}; ${result.impact.invalidated_artifacts.length} downstream artifact classes invalidated.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Edit commit failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="viewer-shell" aria-label="Canonical architectural model editor">
      <div className="viewer-head">
        <div>
          <p className="eyebrow">CANONICAL MODEL EDITOR</p>
          <h2>Revision {revision}</h2>
          <small>Server-authoritative edits with deterministic preview, persistence and scene regeneration.</small>
        </div>
      </div>
      <EditToolbar elementId={selectedNode?.id ?? null} onPreview={preview} onCommit={commit} disabled={busy} />
      {message && <p role="status">{message}</p>}
      <div className="viewer-layout">
        <div className="canvas-wrap three-canvas">
          <SceneCanvas scene={scene} selectedNodeId={selectedNode?.id ?? null} onSelect={setSelectedNode} />
        </div>
        <SceneInspector node={selectedNode} onClear={() => setSelectedNode(null)} />
      </div>
    </section>
  );
}

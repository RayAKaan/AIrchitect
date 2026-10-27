import type { ApiClient } from './client';
import type { EditCommand } from '../../features/scene/EditToolbar';
import { parseScene, type ModelScene } from '../../features/scene/sceneContract';

export type EditPreview = Readonly<{
  read_only: true;
  source_revision: number;
  result_revision: number;
  commands: readonly EditCommand[];
  model: Record<string, unknown>;
}>;

export type EditCommit = Readonly<{
  read_only: false;
  model: { revision: number; model_hash: string; model: Record<string, unknown> };
  impact: {
    previous_hash: string;
    current_hash: string;
    changed_elements: readonly { element_id: string; change_type: string }[];
    affected_elements: readonly string[];
    invalidated_artifacts: readonly string[];
  };
}>;

export async function previewCanonicalEdit(
  api: ApiClient,
  projectId: string,
  expectedRevision: number,
  commands: readonly EditCommand[],
): Promise<EditPreview> {
  return api.request<EditPreview>(`/projects/${encodeURIComponent(projectId)}/model/edit-preview`, {
    method: 'POST',
    body: JSON.stringify({ expected_revision: expectedRevision, commands }),
  });
}

export async function commitCanonicalEdit(
  api: ApiClient,
  projectId: string,
  expectedRevision: number,
  commands: readonly EditCommand[],
  changeSummary = 'Architectural model edit',
): Promise<EditCommit> {
  return api.request<EditCommit>(`/projects/${encodeURIComponent(projectId)}/model/edits`, {
    method: 'POST',
    body: JSON.stringify({ expected_revision: expectedRevision, commands, change_summary: changeSummary }),
  });
}

export async function fetchCanonicalScene(api: ApiClient, projectId: string): Promise<{ revision: number; modelHash: string; scene: ModelScene }> {
  const result = await api.request<{ revision: number; model_hash: string; scene: unknown }>(
    `/projects/${encodeURIComponent(projectId)}/model/scene`,
  );
  return { revision: result.revision, modelHash: result.model_hash, scene: parseScene(result.scene) };
}

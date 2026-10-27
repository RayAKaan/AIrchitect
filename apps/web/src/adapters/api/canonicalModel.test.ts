import { describe, expect, it, vi } from 'vitest';
import type { ApiClient } from './client';
import { commitCanonicalEdit, fetchCanonicalScene, previewCanonicalEdit } from './canonicalModel';

function api(response: unknown): ApiClient {
  return { request: vi.fn().mockResolvedValue(response) };
}

const command = { kind: 'translate' as const, element_id: 'wall-1', dx_m: 1, dy_m: 0, dz_m: 0 };

const scene = {
  model_hash: 'a'.repeat(64),
  nodes: [{ id: 'wall-1', element_type: 'wall', mesh_index: 0, source_model_hash: 'a'.repeat(64), geometry_hash: 'b'.repeat(64) }],
  meshes: [{ element_id: 'wall-1', element_type: 'wall', source_model_hash: 'a'.repeat(64), vertices: [[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces: [[0, 1, 2]], geometry_hash: 'b'.repeat(64) }],
  bounds: { minimum: [0, 0, 0], maximum: [1, 1, 0] },
};

describe('canonical model adapter', () => {
  it('sends preview commands against the expected revision', async () => {
    const client = api({ read_only: true, source_revision: 2, result_revision: 3, commands: [command], model: {} });
    await previewCanonicalEdit(client, 'project/1', 2, [command]);
    expect(client.request).toHaveBeenCalledWith('/projects/project%2F1/model/edit-preview', expect.objectContaining({ method: 'POST' }));
  });

  it('commits edits and returns impact', async () => {
    const client = api({ read_only: false, model: { revision: 3, model_hash: 'c'.repeat(64), model: {} }, impact: { previous_hash: 'a', current_hash: 'c', changed_elements: [], affected_elements: [], invalidated_artifacts: [] } });
    const result = await commitCanonicalEdit(client, 'project-1', 2, [command]);
    expect(result.read_only).toBe(false);
  });

  it('validates the server-derived scene contract', async () => {
    const client = api({ revision: 4, model_hash: scene.model_hash, scene });
    const result = await fetchCanonicalScene(client, 'project-1');
    expect(result.revision).toBe(4);
    expect(result.scene.nodes[0].id).toBe('wall-1');
  });
});

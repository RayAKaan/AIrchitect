import { describe, expect, it } from 'vitest';
import { fetchSystemPreview } from './systemPreview';

const intent = { project_id: 'project-1', site_id: 'site-1', site_width_m: 20, site_depth_m: 30, rooms: [{ room_id: 'living', name: 'Living', target_area_m2: 20 }] } as const;

const response = {
  project_id: 'project-1', read_only: true, model: {}, geometry: [], cad: {}, engineering: {}, quantities: {}, regulatory: {},
  scene: { model_hash: 'm', nodes: [], meshes: [], bounds: { minimum: [0, 0, 0], maximum: [1, 1, 1] } },
};

describe('fetchSystemPreview', () => {
  it('validates the project identity and read-only flag', async () => {
    const client = { request: async () => response };
    const preview = await fetchSystemPreview(client, intent);
    expect(preview.project_id).toBe('project-1');
    expect(preview.read_only).toBe(true);
    expect(preview.scene.modelHash).toBe('m');
  });

  it('rejects a response for a different project', async () => {
    const client = { request: async () => ({ ...response, project_id: 'other' }) };
    await expect(fetchSystemPreview(client, intent)).rejects.toThrow('identity');
  });
});

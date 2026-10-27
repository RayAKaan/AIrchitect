import { describe, expect, it } from 'vitest';
import { parseScene } from './sceneContract';

describe('parseScene', () => {
  it('normalizes the API scene and mesh payload', () => {
    const scene = parseScene({
      model_hash: 'model-1',
      nodes: [{ id: 'wall-1', element_type: 'wall', mesh_index: 0, source_model_hash: 'model-1', geometry_hash: 'geom-1' }],
      meshes: [{ element_id: 'wall-1', element_type: 'wall', source_model_hash: 'model-1', geometry_hash: 'geom-1', vertices: [[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces: [[0, 1, 2]] }],
      bounds: { minimum: [0, 0, 0], maximum: [10, 5, 3] },
    });
    expect(scene.modelHash).toBe('model-1');
    expect(scene.nodes[0].id).toBe('wall-1');
    expect(scene.meshes[0].faces).toEqual([[0, 1, 2]]);
  });

  it('rejects a node pointing outside the mesh collection', () => {
    expect(() => parseScene({ model_hash: 'm', nodes: [{ id: 'x', element_type: 'wall', mesh_index: 2, source_model_hash: 'm', geometry_hash: 'g' }], meshes: [], bounds: { minimum: [0, 0, 0], maximum: [1, 1, 1] } })).toThrow('scene node 0');
  });
});

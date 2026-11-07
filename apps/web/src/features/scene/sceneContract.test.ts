import { describe, expect, it } from 'vitest';
import { parseScene, projectScene } from './sceneContract';

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


describe('canonical scene projections', () => {
  const payload = {
    model_hash: 'model-1',
    nodes: [{ id: 'wall-1', element_type: 'wall', mesh_index: 0, source_model_hash: 'model-1', geometry_hash: 'geom-1' }],
    meshes: [{
      element_id: 'wall-1', element_type: 'wall', source_model_hash: 'model-1', geometry_hash: 'geom-1',
      vertices: [[0, 0, 0], [4, 0, 0], [4, 0, 3], [0, 0, 3]],
      faces: [[0, 1, 2, 3]],
    }],
    bounds: { minimum: [0, 0, 0], maximum: [4, 0, 3] },
  };

  it('projects the same semantic element into plan, front and side coordinates', () => {
    const scene = parseScene(payload);
    expect(projectScene(scene, 'plan').faces[0]).toEqual({
      elementId: 'wall-1',
      points: [[0, 0], [4, 0], [4, 0], [0, 0]],
    });
    expect(projectScene(scene, 'front').faces[0].points).toEqual([
      [0, 0], [4, 0], [4, 3], [0, 3],
    ]);
    expect(projectScene(scene, 'side').faces[0].points).toEqual([
      [0, 0], [0, 0], [0, 3], [0, 3],
    ]);
  });

  it('rejects face indices outside the mesh vertex range', () => {
    const invalid = structuredClone(payload);
    invalid.meshes[0].faces = [[0, 1, 9]];
    expect(() => parseScene(invalid)).toThrow('scene mesh 0 is invalid');
  });

  it('rejects nodes whose semantic identity or geometry lineage differs from the mesh', () => {
    const invalid = structuredClone(payload);
    invalid.nodes[0].geometry_hash = 'stale-geometry';
    expect(() => parseScene(invalid)).toThrow('lineage does not match');
  });
});

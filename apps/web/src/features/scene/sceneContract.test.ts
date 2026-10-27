import { describe, expect, it } from 'vitest';
import { parseScene } from './sceneContract';

describe('parseScene', () => {
  it('normalizes the API scene into a stable client contract', () => {
    const scene = parseScene({
      model_hash: 'model-1',
      nodes: [{ id: 'wall-1', elementType: 'wall', meshIndex: 0, sourceModelHash: 'model-1', geometryHash: 'geom-1' }],
      meshes: [{ vertices: [[0, 0, 0]] }],
      bounds: { minimum: [0, 0, 0], maximum: [10, 5, 3] },
    });
    expect(scene.modelHash).toBe('model-1');
    expect(scene.nodes[0].id).toBe('wall-1');
    expect(scene.bounds.maximum).toEqual([10, 5, 3]);
  });

  it('rejects malformed scene identity', () => {
    expect(() => parseScene({ nodes: [], bounds: { minimum: [0, 0, 0], maximum: [1, 1, 1] } })).toThrow('model_hash');
  });
});

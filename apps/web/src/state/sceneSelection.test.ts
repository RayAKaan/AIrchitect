import { beforeEach, describe, expect, it } from 'vitest';
import { sceneSelection } from './sceneSelection';

describe('sceneSelection', () => {
  beforeEach(() => sceneSelection.clear());

  it('selects and clears a node without losing hover state', () => {
    sceneSelection.hover('wall-1');
    sceneSelection.select('wall-2');
    expect(sceneSelection.getSnapshot()).toEqual({ selectedNodeId: 'wall-2', hoveredNodeId: 'wall-1' });
    sceneSelection.clear();
    expect(sceneSelection.getSnapshot()).toEqual({ selectedNodeId: null, hoveredNodeId: null });
  });
});

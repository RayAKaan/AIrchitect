import { describe, expect, it } from 'vitest';
import { buildEditCommand } from './EditToolbar';

describe('buildEditCommand', () => {
  it('builds deterministic translation commands', () => {
    expect(buildEditCommand('wall-1', 'translate', '2')).toEqual({
      kind: 'translate', element_id: 'wall-1', dx_m: 2, dy_m: 0, dz_m: 0,
    });
  });

  it('builds rotation and resize commands', () => {
    expect(buildEditCommand('wall-1', 'rotate', '90')).toEqual({
      kind: 'rotate', element_id: 'wall-1', angle_deg: 90,
    });
    expect(buildEditCommand('wall-1', 'resize', '0.5')).toEqual({
      kind: 'resize', element_id: 'wall-1', scale: 0.5,
    });
  });

  it('rejects invalid selection and numeric input', () => {
    expect(buildEditCommand(null, 'translate', '2')).toBeNull();
    expect(buildEditCommand('wall-1', 'resize', '0')).toBeNull();
    expect(buildEditCommand('wall-1', 'rotate', 'nope')).toBeNull();
  });
});

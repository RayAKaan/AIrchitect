import { describe, expect, it } from 'vitest';
import { WORKSPACE_SELECTION_EVENT, WORKSPACE_STAGE_EVENT } from './workspaceEvents';

describe('workspace event contract', () => {
  it('uses stable names for stage and selection synchronization', () => {
    expect(WORKSPACE_STAGE_EVENT).toBe('airchitect:workspace-stage');
    expect(WORKSPACE_SELECTION_EVENT).toBe('airchitect:workspace-selection');
  });
});

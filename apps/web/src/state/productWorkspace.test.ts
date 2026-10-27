import { describe, expect, it } from 'vitest';
import { createWorkspaceState, MODE_DEFAULTS, STAGE_MODES, STAGE_TABS, workspaceReducer } from './productWorkspace';

describe('product workspace state', () => {
  it('starts in the simple Brief experience', () => {
    expect(createWorkspaceState('p1')).toMatchObject({ projectId: 'p1', mode: 'Brief', foundationTab: 'S2', advancedStage: 'Brief', advancedOpen: false, versionId: null });
  });

  it('selecting a product mode atomically changes its canonical view', () => {
    const next = workspaceReducer(createWorkspaceState('p1'), { type: 'select-mode', mode: 'Design' });
    expect(next.mode).toBe('Design');
    expect(next.foundationTab).toBe(MODE_DEFAULTS.Design.tab);
    expect(next.advancedStage).toBe(MODE_DEFAULTS.Design.stage);
  });

  it('selecting an advanced stage synchronizes product mode and canonical tab', () => {
    const next = workspaceReducer(createWorkspaceState('p1'), { type: 'select-stage', stage: 'Change Impact' });
    expect(next.advancedOpen).toBe(true);
    expect(next.advancedStage).toBe('Change Impact');
    expect(next.mode).toBe(STAGE_MODES['Change Impact']);
    expect(next.foundationTab).toBe(STAGE_TABS['Change Impact']);
  });

  it('keeps CAD/BIM in the Deliver product mode', () => {
    const next = workspaceReducer(createWorkspaceState('p1'), { type: 'select-stage', stage: 'CAD/BIM Exports' });
    expect(next.mode).toBe('Deliver');
    expect(next.foundationTab).toBe('CAD/BIM Exports');
  });

  it('restores only valid persisted values', () => {
    const state = createWorkspaceState('p1', { mode: 'not-a-mode' as never, foundationTab: 'not-a-tab' as never });
    expect(state.mode).toBe('Brief');
    expect(state.foundationTab).toBe('S2');
  });
});

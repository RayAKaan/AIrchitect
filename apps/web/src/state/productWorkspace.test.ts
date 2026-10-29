import { describe, expect, it } from 'vitest';
import {
  createWorkspaceState,
  MODE_DEFAULTS,
  STAGE_MODES,
  STAGE_TABS,
  readPersistedWorkspace,
  storageKey,
  workspaceReducer,
  persistWorkspace,
  type WorkspaceState,
} from './productWorkspace';

describe('product workspace state', () => {
  it('starts in the simple Brief experience', () => {
    expect(createWorkspaceState('p1')).toMatchObject({
      projectId: 'p1',
      mode: 'Brief',
      foundationTab: 'S2',
      advancedStage: 'Brief',
      advancedOpen: false,
      versionId: null,
    });
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
    const state = createWorkspaceState('p1', {
      mode: 'not-a-mode' as never,
      foundationTab: 'not-a-tab' as never,
      versionId: { unexpected: true } as never,
      advancedOpen: 'yes' as never,
    });
    expect(state.mode).toBe('Brief');
    expect(state.foundationTab).toBe('S2');
    expect(state.versionId).toBeNull();
    expect(state.advancedOpen).toBe(false);
  });

  it('preserves valid advanced tabs when restoring state', () => {
    const state = createWorkspaceState('p1', { foundationTab: 'World Model' });
    expect(state.foundationTab).toBe('World Model');
  });

  it('normalizes invalid version selections to no selected version', () => {
    const initial = createWorkspaceState('p1');
    expect(workspaceReducer(initial, { type: 'select-version', versionId: '  ' }).versionId).toBeNull();
    expect(workspaceReducer(initial, { type: 'select-version', versionId: 'v2' }).versionId).toBe('v2');
  });

  it('round-trips through optional storage without trusting persisted shape', () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => { values.set(key, value); },
    } as Storage;
    const state: WorkspaceState = {
      ...createWorkspaceState('p1'),
      mode: 'Validate',
      advancedStage: 'Regulatory',
      foundationTab: 'Regulatory' as never,
      versionId: 'v4',
      advancedOpen: true,
    };

    persistWorkspace(state, storage);
    expect(readPersistedWorkspace('p1', storage)).toMatchObject({
      projectId: 'p1',
      mode: 'Validate',
      advancedStage: 'Regulatory',
      foundationTab: 'S2',
      versionId: 'v4',
      advancedOpen: true,
    });
    expect(values.has(storageKey('p1'))).toBe(true);
  });

  it('ignores malformed persisted JSON', () => {
    const storage = { getItem: () => '{not-json' } as Storage;
    expect(readPersistedWorkspace('p1', storage)).toBeNull();
  });
});

import { describe, expect, it } from 'vitest';
import { initialWorkspaceState, workspaceReducer } from './workspace';

describe('workspaceReducer', () => {
  it('keeps selection, navigation, and query in explicit UI state', () => {
    const selected = workspaceReducer(initialWorkspaceState, { type: 'select-project', projectId: 'project-1' });
    const navigated = workspaceReducer(selected, { type: 'navigate', navigation: 'Projects' });
    const queried = workspaceReducer(navigated, { type: 'set-project-query', query: 'Riyadh' });

    expect(queried).toEqual({
      activeProjectId: 'project-1',
      activeNavigation: 'Projects',
      projectQuery: 'Riyadh',
    });
  });

  it('does not mutate the previous state', () => {
    const next = workspaceReducer(initialWorkspaceState, { type: 'select-project', projectId: 'project-2' });
    expect(next).not.toBe(initialWorkspaceState);
    expect(initialWorkspaceState.activeProjectId).toBeNull();
  });
});

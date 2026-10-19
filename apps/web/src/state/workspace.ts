export type WorkspaceState = {
  activeProjectId: string | null;
  activeNavigation: 'Overview' | 'Projects' | 'Alternatives' | 'Deliverables' | 'Settings';
  projectQuery: string;
};

export type WorkspaceAction =
  | { type: 'select-project'; projectId: string | null }
  | { type: 'navigate'; navigation: WorkspaceState['activeNavigation'] }
  | { type: 'set-project-query'; query: string };

export const initialWorkspaceState: WorkspaceState = {
  activeProjectId: null,
  activeNavigation: 'Overview',
  projectQuery: '',
};

export function workspaceReducer(state: WorkspaceState, action: WorkspaceAction): WorkspaceState {
  switch (action.type) {
    case 'select-project':
      return { ...state, activeProjectId: action.projectId };
    case 'navigate':
      return { ...state, activeNavigation: action.navigation };
    case 'set-project-query':
      return { ...state, projectQuery: action.query };
    default:
      return state;
  }
}

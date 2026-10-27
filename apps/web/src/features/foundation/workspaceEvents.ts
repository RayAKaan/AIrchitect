export type WorkspaceStageEvent = { stage: string; projectId: string };
export type WorkspaceSelectionEvent = { artifactId: string; projectId: string };

export const WORKSPACE_STAGE_EVENT = 'airchitect:workspace-stage';
export const WORKSPACE_SELECTION_EVENT = 'airchitect:workspace-selection';

export function emitWorkspaceSelection(detail: WorkspaceSelectionEvent) {
  window.dispatchEvent(new CustomEvent<WorkspaceSelectionEvent>(WORKSPACE_SELECTION_EVENT, { detail }));
}

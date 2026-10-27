import { PRODUCT_MODES, type ProductMode } from './productWorkspace';

export type WorkspaceUrlState = { projectId: string | null; mode: ProductMode | null; versionId: string | null };

export function parseWorkspaceUrl(search: string): WorkspaceUrlState {
  const params = new URLSearchParams(search);
  const modeValue = params.get('mode');
  return {
    projectId: params.get('project'),
    mode: PRODUCT_MODES.includes(modeValue as ProductMode) ? modeValue as ProductMode : null,
    versionId: params.get('version'),
  };
}

export function buildWorkspaceUrl(pathname: string, state: { projectId: string; mode: ProductMode; versionId: string | null }): string {
  const params = new URLSearchParams({ project: state.projectId, mode: state.mode });
  if (state.versionId) params.set('version', state.versionId);
  return `${pathname}?${params.toString()}`;
}

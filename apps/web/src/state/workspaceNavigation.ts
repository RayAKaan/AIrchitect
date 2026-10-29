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

export function buildWorkspaceUrl(
  pathname: string,
  state: { projectId: string; mode: ProductMode; versionId: string | null },
  currentSearch = '',
  currentHash = '',
): string {
  const existing = new URLSearchParams(currentSearch);
  const params = new URLSearchParams();
  existing.forEach((value, key) => {
    if (key !== 'project' && key !== 'mode' && key !== 'version') params.append(key, value);
  });
  params.set('project', state.projectId);
  params.set('mode', state.mode);
  if (state.versionId) params.set('version', state.versionId);
  const query = params.toString();
  return pathname + (query ? '?' + query : '') + currentHash;
}

export function clearWorkspaceUrl(currentHref: string): string {
  const url = new URL(currentHref);
  url.searchParams.delete('project');
  url.searchParams.delete('mode');
  url.searchParams.delete('version');
  return url.pathname + url.search + url.hash;
}

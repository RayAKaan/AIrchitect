import { describe, expect, it } from 'vitest';
import { buildWorkspaceUrl, parseWorkspaceUrl } from './workspaceNavigation';

describe('workspace navigation', () => {
  it('parses valid project, mode and version state', () => {
    expect(parseWorkspaceUrl('?project=p1&mode=Design&version=v3')).toEqual({ projectId: 'p1', mode: 'Design', versionId: 'v3' });
  });

  it('rejects unknown modes without losing project/version context', () => {
    expect(parseWorkspaceUrl('?project=p1&mode=Unknown&version=v3')).toEqual({ projectId: 'p1', mode: null, versionId: 'v3' });
  });

  it('serializes workspace state deterministically', () => {
    expect(buildWorkspaceUrl('/workspace', { projectId: 'p1', mode: 'Deliver', versionId: 'v4' })).toBe('/workspace?project=p1&mode=Deliver&version=v4');
  });
});

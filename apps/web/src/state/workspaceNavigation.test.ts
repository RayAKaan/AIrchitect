import { describe, expect, it } from 'vitest';
import { buildWorkspaceUrl, clearWorkspaceUrl, parseWorkspaceUrl } from './workspaceNavigation';

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

  it('preserves unrelated query parameters and the URL fragment', () => {
    expect(buildWorkspaceUrl('/workspace', { projectId: 'p1', mode: 'Design', versionId: null }, '?campaign=summer&mode=Brief&version=old', '#canvas'))
      .toBe('/workspace?campaign=summer&project=p1&mode=Design#canvas');
  });

  it('clears only workspace parameters when leaving a project', () => {
    expect(clearWorkspaceUrl('https://example.test/workspace?campaign=summer&project=p1&mode=Design&version=v4#canvas'))
      .toBe('/workspace?campaign=summer#canvas');
  });
});

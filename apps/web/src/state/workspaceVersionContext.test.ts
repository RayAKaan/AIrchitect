import { describe, expect, it } from 'vitest';
import { resolveVersionContext } from './workspaceVersionContext';

type Version = { id: string; label: string };
type Snapshot = { version: Version; payload: string };

describe('workspace version context', () => {
  const versions: Version[] = [{ id: 'v1', label: 'Version 1' }, { id: 'v2', label: 'Version 2' }];

  it('uses the selected version and matching snapshot', () => {
    const snapshot: Snapshot = { version: versions[1], payload: 'v2 data' };
    expect(resolveVersionContext('v2', versions, snapshot)).toEqual({
      currentVersion: versions[1],
      currentSnapshot: snapshot,
    });
  });

  it('never exposes a snapshot from a previously selected version', () => {
    const staleSnapshot: Snapshot = { version: versions[0], payload: 'stale v1 data' };
    expect(resolveVersionContext('v2', versions, staleSnapshot)).toEqual({
      currentVersion: versions[1],
      currentSnapshot: null,
    });
  });

  it('uses a matching snapshot as fallback while the version list is empty', () => {
    const snapshot: Snapshot = { version: versions[1], payload: 'v2 data' };
    expect(resolveVersionContext('v2', [], snapshot)).toEqual({
      currentVersion: versions[1],
      currentSnapshot: snapshot,
    });
  });

  it('does not select a version or snapshot when no version is selected', () => {
    const snapshot: Snapshot = { version: versions[0], payload: 'v1 data' };
    expect(resolveVersionContext(null, versions, snapshot)).toEqual({
      currentVersion: null,
      currentSnapshot: null,
    });
  });
});

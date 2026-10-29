export type VersionIdentity = { id: string };
export type SnapshotWithVersion<T extends VersionIdentity> = { version: T };

export type ResolvedVersionContext<T extends VersionIdentity> = {
  currentVersion: T | null;
  currentSnapshot: SnapshotWithVersion<T> | null;
};

/**
 * A snapshot is usable only when it belongs to the currently selected version.
 * The version list is authoritative for the picker; a matching snapshot is a
 * fallback while that list is refreshing or when it has not loaded yet.
 */
export function resolveVersionContext<T extends VersionIdentity>(
  selectedVersionId: string | null,
  versions: readonly T[],
  snapshot: SnapshotWithVersion<T> | null,
): ResolvedVersionContext<T> {
  if (!selectedVersionId) {
    return { currentVersion: null, currentSnapshot: null };
  }

  const currentSnapshot = snapshot?.version.id === selectedVersionId ? snapshot : null;
  const currentVersion = versions.find((version) => version.id === selectedVersionId)
    ?? currentSnapshot?.version
    ?? null;

  return { currentVersion, currentSnapshot };
}

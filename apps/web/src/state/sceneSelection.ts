import { useSyncExternalStore } from 'react';

export type SceneSelectionState = Readonly<{
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
}>;

const initialState: SceneSelectionState = { selectedNodeId: null, hoveredNodeId: null };
let state = initialState;
const listeners = new Set<() => void>();

function publish(next: SceneSelectionState): void {
  state = Object.freeze(next);
  listeners.forEach((listener) => listener());
}

export const sceneSelection = {
  getSnapshot: (): SceneSelectionState => state,
  subscribe: (listener: () => void): (() => void) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  select: (nodeId: string | null): void => publish({ ...state, selectedNodeId: nodeId }),
  hover: (nodeId: string | null): void => publish({ ...state, hoveredNodeId: nodeId }),
  clear: (): void => publish(initialState),
};

export function useSceneSelection(): SceneSelectionState {
  return useSyncExternalStore(sceneSelection.subscribe, sceneSelection.getSnapshot, sceneSelection.getSnapshot);
}

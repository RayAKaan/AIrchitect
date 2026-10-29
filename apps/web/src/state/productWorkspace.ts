export const PRODUCT_MODES = ['Brief', 'Site', 'Explore', 'Design', 'Validate', 'Deliver'] as const;
export type ProductMode = (typeof PRODUCT_MODES)[number];

export const ADVANCED_STAGES = ['Brief', 'World Model', 'Semantic Model', 'Design', 'CAD/BIM Exports', 'Engineering', 'Change Impact', 'Release Validation', 'Regulatory'] as const;
export type AdvancedStage = (typeof ADVANCED_STAGES)[number];

export const FOUNDATION_TABS = [
  'S2', 'Site', 'Providers', 'Brief', 'Requirements', 'Assumptions', 'World Model',
  'Semantic Model', 'Design', 'CAD/BIM Exports', 'Change Impact', 'Release Validation',
  'Board', 'New Version', 'Compare',
] as const;
export type FoundationTab = (typeof FOUNDATION_TABS)[number];

export type WorkspaceState = {
  projectId: string;
  mode: ProductMode;
  advancedStage: AdvancedStage;
  foundationTab: FoundationTab;
  versionId: string | null;
  advancedOpen: boolean;
};

export type WorkspaceAction =
  | { type: 'select-mode'; mode: ProductMode }
  | { type: 'select-stage'; stage: AdvancedStage }
  | { type: 'select-tab'; tab: FoundationTab }
  | { type: 'select-version'; versionId: string | null }
  | { type: 'toggle-advanced'; open?: boolean };

export const MODE_DEFAULTS: Record<ProductMode, { tab: FoundationTab; stage: AdvancedStage }> = {
  Brief: { tab: 'S2', stage: 'Brief' },
  Site: { tab: 'Site', stage: 'Brief' },
  Explore: { tab: 'S2', stage: 'Brief' },
  Design: { tab: 'Design', stage: 'Design' },
  Validate: { tab: 'Release Validation', stage: 'Release Validation' },
  Deliver: { tab: 'CAD/BIM Exports', stage: 'CAD/BIM Exports' },
};

export const STAGE_TABS: Record<AdvancedStage, FoundationTab> = {
  Brief: 'S2',
  'World Model': 'World Model',
  'Semantic Model': 'Semantic Model',
  Design: 'Design',
  'CAD/BIM Exports': 'CAD/BIM Exports',
  Engineering: 'Design',
  'Change Impact': 'Change Impact',
  'Release Validation': 'Release Validation',
  Regulatory: 'Release Validation',
};

export const STAGE_MODES: Record<AdvancedStage, ProductMode> = {
  Brief: 'Brief',
  'World Model': 'Brief',
  'Semantic Model': 'Brief',
  Design: 'Design',
  'CAD/BIM Exports': 'Deliver',
  Engineering: 'Design',
  'Change Impact': 'Validate',
  'Release Validation': 'Validate',
  Regulatory: 'Validate',
};

export function isProductMode(value: unknown): value is ProductMode {
  return typeof value === 'string' && PRODUCT_MODES.some((mode) => mode === value);
}

export function isAdvancedStage(value: unknown): value is AdvancedStage {
  return typeof value === 'string' && ADVANCED_STAGES.some((stage) => stage === value);
}

export function isFoundationTab(value: unknown): value is FoundationTab {
  return typeof value === 'string' && FOUNDATION_TABS.some((tab) => tab === value);
}

export function createWorkspaceState(projectId: string, persisted?: Partial<WorkspaceState> | null): WorkspaceState {
  const mode = isProductMode(persisted?.mode) ? persisted.mode : 'Brief';
  const defaults = MODE_DEFAULTS[mode];
  const stage = isAdvancedStage(persisted?.advancedStage) ? persisted.advancedStage : defaults.stage;
  const tab = isFoundationTab(persisted?.foundationTab) ? persisted.foundationTab : defaults.tab;
  const versionId = typeof persisted?.versionId === 'string' && persisted.versionId.trim()
    ? persisted.versionId
    : null;

  return {
    projectId,
    mode,
    advancedStage: stage,
    foundationTab: tab,
    versionId,
    advancedOpen: typeof persisted?.advancedOpen === 'boolean' ? persisted.advancedOpen : false,
  };
}

export function workspaceReducer(state: WorkspaceState, action: WorkspaceAction): WorkspaceState {
  switch (action.type) {
    case 'select-mode': {
      const defaults = MODE_DEFAULTS[action.mode];
      return { ...state, mode: action.mode, foundationTab: defaults.tab, advancedStage: defaults.stage };
    }
    case 'select-stage':
      return {
        ...state,
        mode: STAGE_MODES[action.stage],
        advancedStage: action.stage,
        foundationTab: STAGE_TABS[action.stage],
        advancedOpen: true,
      };
    case 'select-tab':
      return { ...state, foundationTab: action.tab };
    case 'select-version':
      return { ...state, versionId: typeof action.versionId === 'string' && action.versionId.trim() ? action.versionId : null };
    case 'toggle-advanced':
      return { ...state, advancedOpen: action.open ?? !state.advancedOpen };
    default:
      return state;
  }
}

export function storageKey(projectId: string): string {
  return `airchitect:workspace:${projectId}`;
}

export function readPersistedWorkspace(projectId: string, storage: Storage | undefined = typeof sessionStorage === 'undefined' ? undefined : sessionStorage): Partial<WorkspaceState> | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(storageKey(projectId));
    if (!raw) return null;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
    const candidate = value as Partial<WorkspaceState>;
    return createWorkspaceState(projectId, candidate);
  } catch {
    return null;
  }
}

export function persistWorkspace(
  state: WorkspaceState,
  storage: Storage | undefined = typeof sessionStorage === 'undefined' ? undefined : sessionStorage,
): void {
  if (!storage) return;
  try {
    storage.setItem(storageKey(state.projectId), JSON.stringify(state));
  } catch {
    // Storage is optional; workspace navigation remains authoritative in memory.
  }
}

import type { AdvancedStage } from './productWorkspace';

export const ADVANCED_STAGE_VIEW_TARGETS = {
  Brief: 'brief',
  'World Model': 'world-model',
  'Semantic Model': 'semantic-model',
  Design: 'design',
  'CAD/BIM Exports': 'deliver',
  Engineering: 'engineering',
  'Change Impact': 'change-impact',
  'Release Validation': 'release-validation',
  Regulatory: 'regulatory',
} as const satisfies Record<AdvancedStage, string>;

export type AdvancedViewTarget = (typeof ADVANCED_STAGE_VIEW_TARGETS)[AdvancedStage];

/**
 * Keep advanced-stage navigation separate from product-mode navigation.
 * Some stages intentionally share a domain surface (Engineering uses Design;
 * Regulatory uses Release Validation), but remain distinct workflow stages.
 */
export function resolveAdvancedStageView(stage: AdvancedStage): AdvancedViewTarget {
  return ADVANCED_STAGE_VIEW_TARGETS[stage];
}

export function assertUnreachableAdvancedView(value: never): never {
  throw new Error(`Unhandled advanced workspace view: ${String(value)}`);
}

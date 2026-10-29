import { describe, expect, it } from 'vitest';
import { ADVANCED_STAGES } from './productWorkspace';
import {
  ADVANCED_STAGE_VIEW_TARGETS,
  resolveAdvancedStageView,
  type AdvancedViewTarget,
} from './workspaceAdvancedRouting';

describe('advanced workspace routing', () => {
  it('maps every advanced stage to an explicit view target', () => {
    expect(Object.keys(ADVANCED_STAGE_VIEW_TARGETS).sort()).toEqual([...ADVANCED_STAGES].sort());
  });

  it.each([
    ['Brief', 'brief'],
    ['World Model', 'world-model'],
    ['Semantic Model', 'semantic-model'],
    ['Design', 'design'],
    ['CAD/BIM Exports', 'deliver'],
    ['Engineering', 'engineering'],
    ['Change Impact', 'change-impact'],
    ['Release Validation', 'release-validation'],
    ['Regulatory', 'regulatory'],
  ] as const)('routes %s to %s', (stage, target) => {
    expect(resolveAdvancedStageView(stage)).toBe(target);
  });

  it('keeps shared surfaces explicit without collapsing distinct workflow stages', () => {
    expect(resolveAdvancedStageView('Engineering')).toBe('engineering');
    expect(resolveAdvancedStageView('Design')).toBe('design');
    expect(resolveAdvancedStageView('Regulatory')).toBe('regulatory');
    expect(resolveAdvancedStageView('Release Validation')).toBe('release-validation');
    const targets = ADVANCED_STAGES.map(resolveAdvancedStageView);
    expect(new Set<AdvancedViewTarget>(targets).size).toBe(ADVANCED_STAGES.length);
  });
});

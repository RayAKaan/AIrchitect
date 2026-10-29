import { describe, expect, it } from 'vitest';
import { PRODUCT_MODES } from './productWorkspace';
import { MODE_VIEW_TARGETS, resolveModeView, type ModeViewTarget } from './workspaceModeRouting';

describe('six-mode workspace routing', () => {
  it('defines a view target for every product mode', () => {
    expect(Object.keys(MODE_VIEW_TARGETS).sort()).toEqual([...PRODUCT_MODES].sort());
  });

  it.each([
    ['Brief', 'brief'],
    ['Site', 'site'],
    ['Explore', 'explore'],
    ['Design', 'design'],
    ['Validate', 'validate'],
    ['Deliver', 'deliver'],
  ] as const)('routes %s to its dedicated view target', (mode, target) => {
    expect(resolveModeView(mode)).toBe(target);
  });

  it('uses six distinct view targets rather than routing unrelated modes to a fallback', () => {
    const targets = PRODUCT_MODES.map((mode) => resolveModeView(mode));
    expect(new Set<ModeViewTarget>(targets).size).toBe(PRODUCT_MODES.length);
  });
});

import { describe, expect, it } from 'vitest';
import { canEditConstraint, normalizeConstraint, splitConstraints } from './constraints';

describe('design constraints', () => {
  const hard = normalizeConstraint({ label: 'Max height', parameter: 'building_height', value: 30, unit: 'm', strength: 'hard', source: 'regulation', locked: true });
  const soft = normalizeConstraint({ label: 'Prefer parking', parameter: 'parking_spaces', value: 120, strength: 'soft', source: 'human', locked: false });

  it('separates hard constraints from preferences', () => {
    expect(splitConstraints([hard, soft])).toEqual({ hard: [hard], soft: [soft] });
  });

  it('does not allow regulated constraints to be edited', () => {
    expect(canEditConstraint(hard)).toBe(false);
    expect(canEditConstraint(soft)).toBe(true);
  });

  it('rejects blank constraint identity', () => {
    expect(() => normalizeConstraint({ label: ' ', parameter: 'height', value: 30, strength: 'hard', source: 'human', locked: false })).toThrow();
  });
});

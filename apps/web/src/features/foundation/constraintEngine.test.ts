import { describe, expect, it } from 'vitest';
import { detectConflicts, normalizeConstraint, splitConstraints } from './constraintEngine';

describe('constraint engine', () => {
  it('normalizes constraints and splits hard from soft', () => {
    const constraints = [
      normalizeConstraint({ label: 'Max GFA', parameter: 'gfa', value: 8000, unit: 'm²', strength: 'hard', source: 'brief', locked: false }),
      normalizeConstraint({ label: 'Prefer daylight', parameter: 'daylight', value: true, strength: 'soft', source: 'human', locked: false }),
    ];
    expect(splitConstraints(constraints).hard).toHaveLength(1);
    expect(splitConstraints(constraints).soft).toHaveLength(1);
  });

  it('detects conflicting hard constraints for the same parameter', () => {
    const conflicts = detectConflicts([
      normalizeConstraint({ label: 'A', parameter: 'gfa', value: 8000, strength: 'hard', source: 'brief', locked: false }),
      normalizeConstraint({ label: 'B', parameter: 'gfa', value: 9000, strength: 'hard', source: 'human', locked: false }),
    ]);
    expect(conflicts).toEqual(['Conflicting hard constraints for gfa.']);
  });
});

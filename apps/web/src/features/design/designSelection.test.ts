import { describe, expect, it } from 'vitest';
import { confirmConcept, emptySelection, selectConcept } from './designSelection';

describe('design selection', () => {
  it('requires a selected concept before confirmation', () => {
    expect(() => confirmConcept(emptySelection(), 'reason')).toThrow();
  });

  it('resets confirmation when changing concept', () => {
    const first = confirmConcept(selectConcept(emptySelection(), 'a'), 'good trade-off');
    expect(selectConcept(first, 'b')).toEqual({ selectedId: 'b', rationale: 'good trade-off', confirmed: false });
  });
});

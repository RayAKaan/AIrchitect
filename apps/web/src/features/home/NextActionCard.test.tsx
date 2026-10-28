import { describe, expect, it } from 'vitest';
import { chooseAction } from './NextActionCard';

describe('chooseAction', () => {
  it('prioritizes the source brief when none exists', () => {
    const action = chooseAction('Brief', null, 'DRAFT');
    expect(action.title).toBe('Write the project brief');
    expect(action.mode).toBe('Brief');
    expect(action.label).toBe('Open brief');
  });

  it('moves a complete brief toward concept exploration', () => {
    const action = chooseAction('Brief', {
      brief: { raw_text: 'A retail building' },
      requirements: [{ id: 'r1' }],
    }, 'DRAFT');
    expect(action.title).toBe('Explore concepts');
    expect(action.mode).toBe('Explore');
  });
});

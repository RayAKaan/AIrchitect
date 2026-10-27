import { describe, expect, it } from 'vitest';
import { PRODUCT_MODE_TAB, isProductMode, storedProductMode } from './workspaceModes';

describe('workspace modes', () => {
  it('maps every product mode to a canonical foundation surface', () => {
    expect(PRODUCT_MODE_TAB).toEqual({
      Brief: 'Brief',
      Site: 'Site',
      Explore: 'S2',
      Design: 'Design',
      Validate: 'Release Validation',
      Deliver: 'CAD/BIM Exports',
    });
  });

  it('rejects unknown modes', () => {
    expect(isProductMode('Engineering')).toBe(false);
    expect(isProductMode('Explore')).toBe(true);
  });

  it('falls back safely when persisted mode is stale', () => {
    const storage = {
      getItem: () => 'Engineering',
    } as unknown as Storage;
    expect(storedProductMode('project-1', storage)).toBe('Brief');
  });
});

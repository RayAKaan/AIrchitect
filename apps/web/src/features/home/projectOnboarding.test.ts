import { describe, expect, it } from 'vitest';
import { normalizeProjectIntent } from './projectOnboarding';

describe('project onboarding', () => {
  it('keeps the user's intent as the canonical starting brief', () => {
    const draft = normalizeProjectIntent('Six-floor retail centre in Riyadh with 8000 sqm of GFA.');
    expect(draft.name).toBe('Six-floor retail centre in Riyadh with 8000 sqm of GFA');
    expect(draft.buildingType).toBe('retail');
    expect(draft.location).toBe('Riyadh');
    expect(draft.brief).toContain('8000 sqm');
  });

  it('uses safe defaults when intent is underspecified', () => {
    expect(normalizeProjectIntent('A new building').buildingType).toBe('commercial');
    expect(normalizeProjectIntent('A new building').location).toBe('Saudi Arabia');
  });
});

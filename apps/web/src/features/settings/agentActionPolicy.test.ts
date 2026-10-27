import { describe, expect, it } from 'vitest';
import { isSafeToRunAutomatically, requiresHumanApproval } from './agentActionPolicy';

describe('agent action policy', () => {
  it('allows only reads to run automatically', () => {
    expect(isSafeToRunAutomatically('read')).toBe(true);
    expect(isSafeToRunAutomatically('propose')).toBe(false);
    expect(isSafeToRunAutomatically('commit')).toBe(false);
  });

  it('requires approval for proposed and committed changes', () => {
    expect(requiresHumanApproval('read')).toBe(false);
    expect(requiresHumanApproval('propose')).toBe(true);
    expect(requiresHumanApproval('commit')).toBe(true);
  });
});

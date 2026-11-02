import { describe, expect, it } from 'vitest';
import { MAX_AGENT_CONTEXT_CHARACTERS, prepareAgentContext } from './agentContext';

describe('prepareAgentContext', () => {
  it('preserves small canonical context without changing it', () => {
    const context = JSON.stringify({ brief: 'Residential building', requirements: [{ parameter: 'floors', value: 2 }] });
    expect(prepareAgentContext(context)).toBe(context);
  });

  it('compacts large JSON context and keeps the result valid JSON', () => {
    const context = JSON.stringify({
      brief: { raw_text: 'A'.repeat(12000) },
      requirements: Array.from({ length: 100 }, (_, index) => ({ id: index, description: 'B'.repeat(500) })),
      world_model: { payload: 'C'.repeat(24000) },
    });
    const prepared = prepareAgentContext(context);
    expect(prepared.length).toBeLessThanOrEqual(MAX_AGENT_CONTEXT_CHARACTERS);
    expect(JSON.parse(prepared)).toBeTruthy();
    expect(prepared).toContain('Context shortened');
  });

  it('bounds non-JSON context and rejects unusable budgets', () => {
    const prepared = prepareAgentContext('X'.repeat(5000), 1000);
    expect(prepared.length).toBeLessThanOrEqual(1000);
    expect(prepared).toContain('Use AIrchitect MCP tools');
    expect(() => prepareAgentContext('context', 100)).toThrow('at least 512');
  });
});

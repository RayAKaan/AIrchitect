import { describe, expect, it } from 'vitest';
import { buildReleaseGates, summarizeReleaseGates } from './releaseValidationModel';

const hash = 'a'.repeat(64);
function snapshot() {
  return {
    brief: { structured: { _validation: { status: 'PASS', issues: [] } } },
    world_model_revision: { model_hash: hash },
  };
}
function evidence() {
  return {
    versionStatus: 'COMMITTED',
    snapshot: snapshot(),
    semantic: { world_model_hash: hash, consistency_issues: [] },
    exports: { status: 'PASS', world_model_hash: hash, artifacts: [{ exportable: true }] },
    graph: { integrity: 'PASS', rejected_cross_scope_edge_count: 0, nodes: [{ id: 'a' }], edges: [] },
  };
}

describe('Phase 28 release validation model', () => {
  it('passes automated gates only when evidence is current and internally consistent', () => {
    const gates = buildReleaseGates(evidence());
    expect(gates.find(gate => gate.id === 'canonical-version')?.status).toBe('PASS');
    expect(gates.find(gate => gate.id === 'requirements')?.status).toBe('PASS');
    expect(gates.find(gate => gate.id === 'semantic-model')?.status).toBe('PASS');
    expect(gates.find(gate => gate.id === 'cad-exports')?.status).toBe('PASS');
    expect(gates.find(gate => gate.id === 'dependency-graph')?.status).toBe('PASS');
    expect(gates.find(gate => gate.id === 'native-cad-host')?.status).toBe('NOT_VERIFIED');
    expect(summarizeReleaseGates(gates)).toBe('REVIEW_REQUIRED');
  });

  it('does not treat missing export or dependency evidence as a pass', () => {
    const gates = buildReleaseGates({ ...evidence(), exports: { status: 'NO_ARTIFACTS', world_model_hash: hash, artifacts: [] }, graph: { integrity: 'PASS', rejected_cross_scope_edge_count: 0, nodes: [], edges: [] } });
    expect(gates.find(gate => gate.id === 'cad-exports')?.status).toBe('NOT_RUN');
    expect(gates.find(gate => gate.id === 'dependency-graph')?.status).toBe('NOT_RUN');
    expect(summarizeReleaseGates(gates)).toBe('REVIEW_REQUIRED');
  });

  it('flags stale hash bindings and cross-scope graph findings for review', () => {
    const gates = buildReleaseGates({
      ...evidence(),
      semantic: { world_model_hash: 'b'.repeat(64), consistency_issues: [] },
      exports: { status: 'PASS', world_model_hash: hash, artifacts: [{ exportable: false }] },
      graph: { integrity: 'REVIEW_REQUIRED', rejected_cross_scope_edge_count: 1, nodes: [{ id: 'a' }], edges: [] },
    });
    expect(gates.find(gate => gate.id === 'semantic-model')?.status).toBe('REVIEW_REQUIRED');
    expect(gates.find(gate => gate.id === 'cad-exports')?.status).toBe('REVIEW_REQUIRED');
    expect(gates.find(gate => gate.id === 'dependency-graph')?.status).toBe('REVIEW_REQUIRED');
  });

  it('requires review for a draft canonical version', () => {
    const gates = buildReleaseGates({ ...evidence(), versionStatus: 'DRAFT' });
    expect(gates.find(gate => gate.id === 'canonical-version')?.status).toBe('REVIEW_REQUIRED');
  });
});

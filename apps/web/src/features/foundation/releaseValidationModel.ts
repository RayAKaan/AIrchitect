export type ReleaseGateStatus = 'PASS' | 'BLOCKED' | 'REVIEW_REQUIRED' | 'NOT_RUN' | 'UNKNOWN' | 'NOT_VERIFIED';
export type ReleaseGate = { id: string; title: string; status: ReleaseGateStatus; detail: string; evidence?: string };

type Input = { versionStatus: string; snapshot: any; semantic: any | null; exports: any | null; graph: any | null };

function worldHash(snapshot: any): string {
  return snapshot?.world_model_revision?.model_hash || snapshot?.world_model?.model_hash || '';
}

export function buildReleaseGates(input: Input): ReleaseGate[] {
  const currentHash = worldHash(input.snapshot);
  const briefValidation = input.snapshot?.brief?.structured?._validation
    || input.snapshot?.brief?.structured_json?._validation || null;
  const gates: ReleaseGate[] = [];

  gates.push({
    id: 'canonical-version',
    title: 'Canonical World Model',
    status: input.versionStatus === 'COMMITTED' ? 'PASS' : 'REVIEW_REQUIRED',
    detail: input.versionStatus === 'COMMITTED'
      ? 'The selected project version is committed and has an immutable canonical revision.'
      : 'Commit and review the selected draft before treating downstream evidence as release-ready.',
    evidence: currentHash ? 'SHA-256 ' + currentHash : 'No canonical World Model hash is available.',
  });

  const qualityStatus = String(briefValidation?.status || '').toUpperCase();
  const qualityMap: Record<string, ReleaseGateStatus> = { PASS: 'PASS', BLOCKED: 'BLOCKED', REVIEW_REQUIRED: 'REVIEW_REQUIRED' };
  gates.push({
    id: 'requirements',
    title: 'Requirement quality',
    status: qualityMap[qualityStatus] || (briefValidation ? 'UNKNOWN' : 'NOT_RUN'),
    detail: !briefValidation
      ? 'No persisted automated requirement-quality report is available for this brief.'
      : String(briefValidation.issues?.length || 0) + ' recorded quality issue(s); extracted values still require human confirmation.',
    evidence: briefValidation ? 'Validator status: ' + qualityStatus : 'No validation evidence',
  });

  if (!input.semantic) {
    gates.push({ id: 'semantic-model', title: 'Semantic model integrity', status: 'UNKNOWN', detail: 'The semantic model endpoint did not provide evidence.' });
  } else {
    const semanticHash = input.semantic.world_model_hash || '';
    const issueCount = (input.semantic.consistency_issues || []).length;
    const matches = Boolean(currentHash && semanticHash === currentHash);
    gates.push({
      id: 'semantic-model', title: 'Semantic model integrity',
      status: !matches || issueCount > 0 ? 'REVIEW_REQUIRED' : 'PASS',
      detail: !matches
        ? 'The semantic model hash is missing or does not match the selected canonical World Model.'
        : issueCount > 0
          ? issueCount + ' semantic consistency finding(s) require review.'
          : 'Semantic model hash matches the selected canonical World Model; no consistency findings were returned.',
      evidence: semanticHash ? 'SHA-256 ' + semanticHash : 'No semantic model hash',
    });
  }

  if (!input.exports) {
    gates.push({ id: 'cad-exports', title: 'CAD/BIM export manifest', status: 'UNKNOWN', detail: 'The export manifest endpoint did not provide evidence.' });
  } else {
    const artifacts = Array.isArray(input.exports.artifacts) ? input.exports.artifacts : [];
    const manifestMatches = Boolean(currentHash && input.exports.world_model_hash === currentHash);
    const allExportable = artifacts.length > 0 && artifacts.every((artifact: any) => artifact.exportable === true);
    const anyBlocked = artifacts.some((artifact: any) => artifact.exportable !== true);
    const status: ReleaseGateStatus = !manifestMatches
      ? 'REVIEW_REQUIRED'
      : artifacts.length === 0
        ? 'NOT_RUN'
        : allExportable && input.exports.status === 'PASS'
          ? 'PASS'
          : anyBlocked ? 'REVIEW_REQUIRED' : 'UNKNOWN';
    gates.push({
      id: 'cad-exports', title: 'CAD/BIM export manifest', status,
      detail: !manifestMatches
        ? 'The export manifest is not bound to the selected canonical World Model hash.'
        : artifacts.length === 0
          ? 'No CAD/BIM artifacts exist for this version; export validation has not run on a deliverable.'
          : allExportable
            ? artifacts.length + ' artifact(s) are marked exportable by format/integrity checks; this is not round-trip certification.'
            : 'One or more exports are stale, corrupt, unsupported, or review-required and cannot be treated as validated.',
      evidence: artifacts.length + ' artifact(s); manifest status ' + (input.exports.status || 'unknown'),
    });
  }

  if (!input.graph) {
    gates.push({ id: 'dependency-graph', title: 'Dependency graph integrity', status: 'UNKNOWN', detail: 'The persisted dependency graph endpoint did not provide evidence.' });
  } else {
    const nodes = Array.isArray(input.graph.nodes) ? input.graph.nodes : [];
    const graphPass = input.graph.integrity === 'PASS' && Number(input.graph.rejected_cross_scope_edge_count || 0) === 0;
    gates.push({
      id: 'dependency-graph', title: 'Dependency graph integrity',
      status: !graphPass ? 'REVIEW_REQUIRED' : nodes.length === 0 ? 'NOT_RUN' : 'PASS',
      detail: !graphPass
        ? 'The graph contains rejected cross-scope edges or integrity findings; inspect before relying on propagation.'
        : nodes.length === 0
          ? 'No persisted artifacts are registered yet; graph traversal has no lineage to validate.'
          : nodes.length + ' persisted artifact(s) and ' + (input.graph.edges || []).length + ' dependency edge(s) are visible in the selected version.',
      evidence: nodes.length + ' node(s); ' + (input.graph.edges || []).length + ' edge(s)',
    });
  }

  gates.push({
    id: 'native-cad-host', title: 'Native CAD-host smoke verification', status: 'NOT_VERIFIED',
    detail: 'This gate requires a successful smoke run on the supported deployment host. Hosted CI and format-level checks cannot prove the native toolchain is installed and operating there.',
  });
  gates.push({
    id: 'legal-clearance', title: 'Legal redistribution clearance', status: 'NOT_VERIFIED',
    detail: 'Complete third-party notices/source materials and qualified legal sign-off must be recorded outside automated CI. A licence-policy pass is not legal approval.',
  });
  return gates;
}

export function summarizeReleaseGates(gates: ReleaseGate[]): ReleaseGateStatus {
  if (gates.some(gate => gate.status === 'BLOCKED')) return 'BLOCKED';
  return gates.every(gate => gate.status === 'PASS') ? 'PASS' : 'REVIEW_REQUIRED';
}

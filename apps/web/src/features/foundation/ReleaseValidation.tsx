import { useCallback, useEffect, useMemo, useState } from 'react';
import { buildReleaseGates, summarizeReleaseGates } from './releaseValidationModel';

type Props = { api: string; token: string; projectId: string; version: { id: string; status: string }; snapshot: any };

export default function ReleaseValidation({ api, token, projectId, version, snapshot }: Props) {
  const [evidence, setEvidence] = useState<{ semantic: any | null; exports: any | null; graph: any | null }>({
    semantic: null, exports: null, graph: null,
  });
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setErrors([]);
    const base = '/projects/' + projectId + '/versions/' + version.id;
    const paths = [base + '/semantic-model', base + '/cad/exports', base + '/change-impact/graph'];
    const results = await Promise.allSettled(paths.map(async path => {
      const response = await fetch(api + path, { headers: { Authorization: 'Bearer ' + token } });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error?.message || data.detail || 'Request failed (' + response.status + ')');
      return data;
    }));
    const keys = ['semantic', 'exports', 'graph'] as const;
    const next: { semantic: any | null; exports: any | null; graph: any | null } = { semantic: null, exports: null, graph: null };
    const failed: string[] = [];
    results.forEach((result, index) => {
      const key = keys[index];
      if (result.status === 'fulfilled') next[key] = result.value;
      else failed.push(key + ': ' + (result.reason instanceof Error ? result.reason.message : 'evidence unavailable'));
    });
    setEvidence(next);
    setErrors(failed);
    setLoading(false);
  }, [api, token, projectId, version.id]);

  useEffect(() => { void load(); }, [load]);

  const gates = useMemo(() => buildReleaseGates({
    versionStatus: version.status, snapshot, ...evidence,
  }), [version.status, snapshot, evidence]);
  const overall = summarizeReleaseGates(gates);

  return <section className="release-validation-workspace">
    <article className="phase-card">
      <header className="release-validation-header">
        <div><p className="eyebrow">PHASE 28 / EVIDENCE-BASED RELEASE CHECK</p><h2>Release validation checklist</h2>
          <p className="muted">A traceable readiness summary for this project version, not a design or regulatory certification.</p></div>
        <button className="btn outline" disabled={loading} onClick={() => void load()}>{loading ? 'Refreshing…' : 'Refresh evidence'}</button>
      </header>
      <div className={'quality-report ' + overall.toLowerCase()} role="status">
        <strong>Overall status: {overall.replaceAll('_', ' ')}</strong>
        <p>{gates.filter(gate => gate.status !== 'PASS').length} gate(s) remain open or require review.</p>
        <small>Evidence is scoped to the selected version and its current World Model hash where the source provides that binding.</small>
      </div>
      {errors.length > 0 && <div className="editor-notice" role="alert"><b>Evidence sources unavailable</b><ul>{errors.map(error => <li key={error}>{error}</li>)}</ul>Unavailable sources remain UNKNOWN; they are not treated as passing.</div>}
      {loading && <p role="status" className="muted">Collecting version-bound release evidence…</p>}
      <div className="phase-grid">
        {gates.map(gate => <article className="release-gate" key={gate.id}>
          <div className="release-gate-head"><h3>{gate.title}</h3><span className={'state ' + gate.status.toLowerCase()}>{gate.status.replaceAll('_', ' ')}</span></div>
          <p>{gate.detail}</p>{gate.evidence && <small>{gate.evidence}</small>}
        </article>)}
      </div>
      <div className="release-validation-note">
        <b>Manual release gates remain explicit.</b> Native CAD-host smoke verification and legal redistribution clearance cannot be inferred from unit tests, hosted CI, format markers, or dependency licence metadata. Structural adequacy, building-code compliance, fire/life safety, and constructability are outside this checklist.
      </div>
    </article>
  </section>;
}

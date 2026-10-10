import { useCallback, useEffect, useState } from 'react';

type Version = { id: string; status: string };
type GraphNode = {
  artifact_version_id: string; artifact_type: string; status: string; output_hash: string;
  world_model_revision_id: string | null; world_model_current: boolean; depends_on: string[]; immutable_payload: boolean;
};
type DependencyGraph = {
  project_id: string; project_version_id: string; world_model_hash: string; nodes: GraphNode[];
  edges: { artifact_version_id: string; depends_on_artifact_version_id: string; dependency_kind: string }[];
  rejected_cross_scope_edge_count: number; integrity: string;
};
type PropagationResult = {
  changed_artifact_ids: string[];
  affected: { artifact_version_id: string; artifact_type: string; previous_status: string; resulting_status: string; dependency_path: string[] }[];
  newly_stale_artifact_ids: string[]; atomic: boolean; recomputation_scheduled: boolean; reason: string;
};

export default function ChangeImpactPanel({ api, token, projectId, version }: {
  api: string; token: string; projectId: string; version: Version;
}) {
  const [graph, setGraph] = useState<DependencyGraph | null>(null);
  const [selectedRoots, setSelectedRoots] = useState<string[]>([]);
  const [reason, setReason] = useState('Reviewed source change requires downstream reassessment');
  const [result, setResult] = useState<PropagationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [propagating, setPropagating] = useState(false);
  const [error, setError] = useState('');

  const call = useCallback(async (path: string, init: RequestInit = {}) => {
    const response = await fetch(api + path, {
      ...init,
      headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json', ...init.headers },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error?.message || data.detail?.error?.message || data.detail || 'Request failed (' + response.status + ')');
    return data;
  }, [api, token]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await call('/projects/' + projectId + '/versions/' + version.id + '/change-impact/graph');
      setGraph(data);
      setSelectedRoots(current => current.filter(id => data.nodes.some((node: GraphNode) => node.artifact_version_id === id)));
    } catch (e) {
      setGraph(null);
      setError(e instanceof Error ? e.message : 'Could not load the persisted dependency graph');
    } finally {
      setLoading(false);
    }
  }, [call, projectId, version.id]);

  useEffect(() => { void load(); }, [load]);

  async function propagate() {
    if (!graph || !selectedRoots.length || reason.trim().length < 3) return;
    setPropagating(true);
    setError('');
    try {
      const payload = await call('/projects/' + projectId + '/versions/' + version.id + '/change-impact/propagate', {
        method: 'POST',
        body: JSON.stringify({
          changed_artifact_ids: selectedRoots,
          expected_world_model_hash: graph.world_model_hash,
          reason: reason.trim(),
        }),
      });
      setResult(payload);
      setSelectedRoots([]);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Change propagation failed');
    } finally {
      setPropagating(false);
    }
  }

  const canPropagate = version.status === 'COMMITTED' && Boolean(graph?.world_model_hash) &&
    selectedRoots.length > 0 && reason.trim().length >= 3 && !loading && !propagating;

  return <section className="change-impact-workspace">
    <article className="phase-card">
      <div className="card-actions">
        <div><p className="eyebrow">PHASE 27 / PERSISTED LINEAGE</p><h2>Dependency graph &amp; change propagation</h2></div>
        <button className="btn outline" disabled={loading || propagating} onClick={() => void load()}>{loading ? 'Refreshing…' : 'Refresh graph'}</button>
      </div>
      <p className="muted">This view reads the server-owned dependency graph for the selected project version. The client cannot supply graph topology.</p>
      {error && <div className="alert" role="alert">{error}</div>}
      {loading && <p role="status" className="muted">Loading persisted dependency graph…</p>}
      {graph && <>
        <div className="change-impact-summary">
          <span className={'state ' + graph.integrity.toLowerCase()}>Graph integrity: {graph.integrity.replaceAll('_', ' ')}</span>
          <span>{graph.nodes.length} artifacts</span><span>{graph.edges.length} dependency edges</span>
          <span>Rejected cross-scope edges: {graph.rejected_cross_scope_edge_count}</span>
        </div>
        <p>World Model hash: <code>{graph.world_model_hash || '—'}</code></p>
        {graph.integrity !== 'PASS' && <div className="editor-notice" role="status">Cross-scope or integrity findings need review. Rejected edges are not traversed.</div>}
        {version.status !== 'COMMITTED' && <div className="editor-notice">Propagation is disabled until the selected version is committed and its World Model hash is stable.</div>}
        {graph.nodes.length === 0 ? <div className="empty-state"><h3>No persisted artifact dependencies yet</h3><p>Generate and persist downstream artifacts to populate this graph. The panel will not invent dependency edges.</p></div> :
          <div className="impact-node-list" aria-label="Persisted artifacts">
            {graph.nodes.map(node => <label className="impact-node" key={node.artifact_version_id}>
              <input type="checkbox" aria-label={'Change root ' + node.artifact_type + ' ' + node.artifact_version_id}
                checked={selectedRoots.includes(node.artifact_version_id)}
                disabled={version.status !== 'COMMITTED' || propagating || loading}
                onChange={event => setSelectedRoots(current => event.target.checked
                  ? [...current, node.artifact_version_id]
                  : current.filter(id => id !== node.artifact_version_id))}/>
              <span><b>{node.artifact_type.replaceAll('_', ' ')}</b><small>{node.artifact_version_id}</small>
                <small>Source revision: {node.world_model_revision_id || 'unknown'} · {node.world_model_current ? 'current source' : 'source differs from current'}</small>
                <small>Dependencies: {node.depends_on.length ? node.depends_on.join(', ') : 'none recorded'}</small></span>
              <span className={'state ' + node.status.toLowerCase()}>{node.status.toUpperCase()}</span>
            </label>)}
          </div>}
        {graph.nodes.length > 0 && <div className="phase-card">
          <p className="eyebrow">EXPLICIT CHANGE EVENT</p><h3>Mark downstream artifacts stale</h3>
          <label className="impact-reason">Reason / audit note
            <textarea value={reason} maxLength={500} onChange={event => setReason(event.target.value)} disabled={propagating}/>
          </label>
          <button className="btn primary" disabled={!canPropagate} onClick={() => void propagate()}>{propagating ? 'Propagating…' : 'Propagate stale status'}</button>
          <p className="muted">Requires at least one selected root and the current World Model hash. Existing payloads and hashes remain immutable; recomputation is not scheduled.</p>
        </div>}
      </>}
      {result && <div className="quality-report review_required" role="status">
        <strong>Propagation recorded · {result.newly_stale_artifact_ids.length} newly stale artifacts</strong>
        <p>{result.affected.length} affected artifacts; transaction atomicity reported as {String(result.atomic)}.</p>
        <p>Recomputation scheduled: {String(result.recomputation_scheduled)}. Reason: {result.reason}</p>
        {result.affected.map(item => <div className="prov-row" key={item.artifact_version_id}><b>{item.artifact_type} · {item.resulting_status}</b><span>{item.dependency_path.join(' → ')}</span></div>)}
      </div>}
    </article>
  </section>;
}

import { useCallback, useEffect, useState } from 'react';

type Props = { api: string; token: string; projectId: string; version: any };

export default function S2ConceptGenerationWorkspace({ api, token, projectId, version }: Props) {
  const [generation, setGeneration] = useState<any>(null);
  const [alternatives, setAlternatives] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const response = await fetch(api + path, {
      ...init,
      headers: {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        Authorization: 'Bearer ' + token,
        ...init.headers,
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw Error(data.detail?.message || data.detail || data.error?.message || ('Request failed (' + response.status + ')'));
    }
    return data;
  }, [api, token]);

  const load = useCallback(async () => {
    const data = await request('/projects/' + projectId + '/versions/' + version.id + '/design/alternatives');
    setAlternatives(data.alternatives || []);
  }, [projectId, request, version.id]);

  async function generate() {
    setBusy(true);
    setError('');
    try {
      const data = await request('/projects/' + projectId + '/versions/' + version.id + '/concepts/generate', {
        method: 'POST',
      });
      setGeneration(data);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Concept generation failed');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load().catch((cause) => setError(cause instanceof Error ? cause.message : 'Could not load alternatives'));
  }, [load]);

  const blocked = version.status !== 'COMMITTED';
  const currentCount = alternatives.filter((alternative) => ['VALID', 'SELECTED'].includes(alternative.status)).length;

  return (
    <div className="phase-card">
      <div className="workflow-head">
        <div>
          <p className="eyebrow">S2 / CONCEPT GENERATION</p>
          <h2>Generate alternatives</h2>
          <p className="muted">
            Concepts are generated from the current architectural programme and planning envelope.
            AIrchitect validates area and height limits and preserves the exact source lineage.
          </p>
        </div>
        <span className={'requirement-state ' + (blocked ? 'proposed' : 'confirmed')}>
          {blocked ? 'COMMIT REQUIRED' : 'READY'}
        </span>
      </div>

      {error && <div className="alert" role="alert">{error}</div>}
      {blocked && (
        <div className="alert">
          Commit the current World Model before concept generation. Programme and envelope artifacts must also be current.
        </div>
      )}

      <div className="card-actions">
        <button className="btn primary" disabled={busy || blocked} onClick={generate}>
          {busy ? 'Generating…' : 'Generate concepts'}
        </button>
        {generation && <span>Generation {String(generation.generation_id || '').slice(0, 12)} · {generation.status}</span>}
      </div>

      {generation?.selection_notice && <p className="muted">{generation.selection_notice}</p>}
      {generation?.program_hash && (
        <div className="prov-row"><b>Programme hash</b><code>{generation.program_hash.slice(0, 16)}…</code></div>
      )}
      {generation?.envelope_hash && (
        <div className="prov-row"><b>Envelope hash</b><code>{generation.envelope_hash.slice(0, 16)}…</code></div>
      )}

      <div className="metric-row">
        <article className="metric-card">
          <div className="metric-top">CURRENT ALTERNATIVES</div>
          <div className="metric-value">{currentCount}</div>
          <div className="metric-foot">Valid or selected against current inputs</div>
        </article>
        <article className="metric-card">
          <div className="metric-top">WORLD MODEL HASH</div>
          <div className="metric-value text-value"><code>{generation?.world_model_hash?.slice(0, 12) || '—'}</code></div>
          <div className="metric-foot">Canonical input</div>
        </article>
      </div>

      {alternatives.length > 0 && (
        <div className="phase-grid">
          {alternatives.map((alternative) => (
            <article className="fact-card" key={alternative.id}>
              <p className="eyebrow">{alternative.strategy_id}</p>
              <h3>{alternative.name}</h3>
              <p>{alternative.description}</p>
              <div className={'requirement-state ' + String(alternative.status).toLowerCase()}>{alternative.status}</div>
              <small>Design hash · {alternative.design_hash?.slice(0, 16)}…</small>
            </article>
          ))}
        </div>
      )}

      <small>
        Alternatives include a programme schedule and preliminary massing metrics. Room-level floor plans,
        exact irregular-polygon placement, planning approval and professional certification are not claimed.
      </small>
    </div>
  );
}

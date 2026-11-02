import { useCallback, useEffect, useState } from 'react';

type Alternative = {
  id: string;
  strategy_id: string;
  name: string;
  description: string;
  status: string;
  metrics?: Record<string, unknown>;
  constraint_results?: Array<Record<string, unknown>>;
  tradeoffs?: Array<{ metric: string; value: unknown; effect: string }>;
  assumptions?: unknown[];
  unknowns?: unknown[];
  provenance?: {
    design_direction_approval?: {
      status?: string;
      approved_at?: string;
      reason?: string;
    };
  };
  evaluation?: {
    comparable: boolean;
    constraint_summary: { pass: number; fail: number; unknown: number };
    pareto_status: string;
    dominated_by: string[];
    note: string;
  };
};

type Props = { api: string; token: string; projectId: string; version: { id: string } };

function messageFor(response: Response, data: any, fallback: string): string {
  if (typeof data?.detail?.message === 'string') return data.detail.message;
  if (typeof data?.detail === 'string') return data.detail;
  if (typeof data?.error?.message === 'string') return data.error.message;
  return fallback + ' (' + response.status + ')';
}

export default function S2ConceptExplorer({ api, token, projectId, version }: Props) {
  const [alternatives, setAlternatives] = useState<Alternative[]>([]);
  const [selected, setSelected] = useState('');
  const [reason, setReason] = useState('');
  const [approvalReason, setApprovalReason] = useState('');
  const [approvalMessage, setApprovalMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch(api + '/projects/' + projectId + '/versions/' + version.id + '/design/comparison', {
        headers: { Authorization: 'Bearer ' + token },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw Error(messageFor(response, data, 'Could not load concepts'));
      const next = Array.isArray(data.alternatives) ? data.alternatives : [];
      setAlternatives(next);
      const serverSelection = next.find((alternative: Alternative) => alternative.status === 'SELECTED');
      setSelected(serverSelection?.id ?? '');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load concepts');
    } finally {
      setLoading(false);
    }
  }, [api, projectId, token, version.id]);

  useEffect(() => { void load(); }, [load]);

  async function recordSelection() {
    if (!selected || reason.trim().length < 3 || busy) return;
    setBusy(true);
    setError('');
    setApprovalMessage('');
    try {
      const response = await fetch(api + '/projects/' + projectId + '/versions/' + version.id + '/design/alternatives/' + selected + '/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
        body: JSON.stringify({ reason: reason.trim() }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw Error(messageFor(response, data, 'Could not select concept'));
      setReason('');
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Selection failed');
    } finally {
      setBusy(false);
    }
  }

  async function approveDirection() {
    if (!selected || approvalReason.trim().length < 3 || busy) return;
    setBusy(true);
    setError('');
    setApprovalMessage('');
    try {
      const response = await fetch(api + '/projects/' + projectId + '/versions/' + version.id + '/design/alternatives/' + selected + '/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
        body: JSON.stringify({ reason: approvalReason.trim() }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw Error(messageFor(response, data, 'Could not approve design direction'));
      setApprovalReason('');
      setApprovalMessage(data.notice || 'Design direction approval recorded.');
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Approval failed');
    } finally {
      setBusy(false);
    }
  }

  const active = alternatives.find((alternative) => alternative.id === selected);
  const approval = active?.provenance?.design_direction_approval;

  return (
    <div className="phase-card" aria-busy={loading || busy}>
      <div className="workflow-head">
        <div>
          <p className="eyebrow">S2 / CONCEPT EXPLORER</p>
          <h2>Evaluate and compare design directions</h2>
          <p className="muted">
            Compare explicit constraints and Pareto trade-offs, record a human selection, then obtain a separate
            project-owner approval for continued design development.
          </p>
        </div>
        <span className="requirement-state confirmed">HUMAN DECISION</span>
      </div>

      {error && <div className="alert" role="alert">{error}</div>}
      {approvalMessage && <div className="settings-status connected" role="status">{approvalMessage}</div>}

      {loading ? (
        <div className="empty-state" role="status"><h3>Loading alternatives…</h3><p>Reading the current canonical design set.</p></div>
      ) : alternatives.length === 0 ? (
        <div className="empty-state"><h3>No current alternatives</h3><p>Generate concepts first, then return here to compare them.</p></div>
      ) : (
        <div className="phase-grid">
          {alternatives.map((alternative) => {
            const isSelected = selected === alternative.id;
            const summary = alternative.evaluation?.constraint_summary;
            return (
              <article className={'fact-card ' + (isSelected ? 'selected-card' : '')} key={alternative.id} aria-label={alternative.name}>
                <div className="workflow-head">
                  <div><p className="eyebrow">{alternative.strategy_id}</p><h3>{alternative.name}</h3></div>
                  <div className={'requirement-state ' + String(alternative.status).toLowerCase()}>{alternative.status}</div>
                </div>
                <p>{alternative.description}</p>
                <dl>
                  {Object.entries(alternative.metrics ?? {}).map(([key, value]) => (
                    <div className="prov-row" key={key}><b>{key.replaceAll('_', ' ')}</b><span>{String(value ?? '—')}</span></div>
                  ))}
                </dl>
                {(alternative.constraint_results?.length ?? 0) > 0 && (
                  <section aria-label="Individual constraint results">
                    <p><strong>Constraint results</strong></p>
                    {alternative.constraint_results?.map((check, index) => (
                      <div className="prov-row" key={String(check.parameter || index)}>
                        <b>{String(check.parameter || 'Constraint').replaceAll('_', ' ')}</b>
                        <span>{String(check.status || 'UNKNOWN')}</span>
                      </div>
                    ))}
                  </section>
                )}
                {summary && (
                  <section aria-label="Constraint evaluation">
                    <p><strong>Constraint checks</strong></p>
                    <div className="prov-row"><b>Passed</b><span>{summary.pass}</span></div>
                    <div className="prov-row"><b>Failed</b><span>{summary.fail}</span></div>
                    <div className="prov-row"><b>Unknown</b><span>{summary.unknown}</span></div>
                    <div className="prov-row"><b>Multi-criteria position</b><span>{alternative.evaluation?.pareto_status}</span></div>
                    {(alternative.evaluation?.dominated_by?.length ?? 0) > 0 && (
                      <small>Dominated by: {alternative.evaluation?.dominated_by?.join(', ')}</small>
                    )}
                  </section>
                )}
                {(alternative.tradeoffs?.length ?? 0) > 0 && <>
                  <p><strong>Trade-offs</strong></p>
                  {alternative.tradeoffs?.map((tradeoff, index) => (
                    <small key={tradeoff.metric + '-' + index}>{tradeoff.metric}: {String(tradeoff.value)} — {tradeoff.effect}<br /></small>
                  ))}
                </>}
                <small>Assumptions: {alternative.assumptions?.length ?? 0} · Unknowns: {alternative.unknowns?.length ?? 0}</small>
                {(alternative.unknowns?.length ?? 0) > 0 && (
                  <small>Outstanding unknowns: {alternative.unknowns?.join(', ')}</small>
                )}
                {alternative.provenance?.design_direction_approval?.status && (
                  <div className="requirement-state confirmed">DESIGN DIRECTION APPROVED</div>
                )}
                <button
                  className="btn outline small"
                  onClick={() => { setSelected(alternative.id); setApprovalMessage(''); }}
                  disabled={!['VALID', 'SELECTED'].includes(alternative.status) || busy}
                  aria-pressed={isSelected}
                >
                  {isSelected ? 'Selected for review' : 'Choose'}
                </button>
              </article>
            );
          })}
        </div>
      )}

      {active && <section className="phase-card" aria-labelledby="design-direction-title">
        <p className="eyebrow">DESIGN-DIRECTION DECISION</p>
        <h3 id="design-direction-title">{active.name}</h3>
        {active.status !== 'SELECTED' ? (
          <>
            <label>Why this direction?
              <textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={3} maxLength={2000} placeholder="Record the design rationale…" aria-describedby="decision-help" />
            </label>
            <div className="card-actions">
              <button className="btn primary" disabled={busy || reason.trim().length < 3} onClick={() => void recordSelection()}>
                {busy ? 'Saving…' : 'Record selection'}
              </button>
              <span id="decision-help">The rationale becomes part of the project decision history.</span>
            </div>
          </>
        ) : approval?.status ? (
          <div className="settings-status connected" role="status">
            Approved for continued design development. {approval.approved_at ? 'Recorded ' + approval.approved_at : ''}
          </div>
        ) : (
          <>
            <label>Approval rationale
              <textarea value={approvalReason} onChange={(event) => setApprovalReason(event.target.value)} minLength={3} maxLength={2000} placeholder="Explain why this selected direction is approved for continued development…" />
            </label>
            <div className="card-actions">
              <button className="btn primary" disabled={busy || approvalReason.trim().length < 3} onClick={() => void approveDirection()}>
                {busy ? 'Saving…' : 'Approve design direction'}
              </button>
              <span>Project owners and organization admins only.</span>
            </div>
            <small>This approval does not constitute planning, code, engineering or construction approval.</small>
          </>
        )}
      </section>}

      <small>No weighted overall score or automatic optimum is claimed. Final design direction remains a human decision.</small>
    </div>
  );
}

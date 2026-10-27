import { useMemo, useState } from 'react';
import './copilot.css';

import {
  CopilotApiClient,
  CopilotApiError,
  type CopilotAcceptanceResponse,
  type CopilotPlanPreviewResponse,
  type CopilotPreviewResponse,
} from './api';

export interface CopilotPanelProps {
  apiBaseUrl: string;
  token: string;
  projectId: string;
  versionId: string;
  revisionHash: string;
  onCommitted?: () => void | Promise<void>;
}

type Stage = 'idle' | 'previewing' | 'planned' | 'approval' | 'accepted' | 'committing' | 'committed' | 'error';

export default function CopilotPanel({ apiBaseUrl, token, projectId, versionId, revisionHash, onCommitted }: CopilotPanelProps) {
  const [question, setQuestion] = useState('');
  const [preview, setPreview] = useState<CopilotPreviewResponse | null>(null);
  const [plan, setPlan] = useState<CopilotPlanPreviewResponse | null>(null);
  const [acceptance, setAcceptance] = useState<CopilotAcceptanceResponse | null>(null);
  const [approvalToken, setApprovalToken] = useState('');
  const [stage, setStage] = useState<Stage>('idle');
  const [error, setError] = useState('');

  const client = useMemo(() => new CopilotApiClient({ apiBaseUrl, token }), [apiBaseUrl, token]);
  const canPreview = question.trim().length > 0 && stage !== 'previewing' && stage !== 'committing';
  const canApprove = Boolean(preview?.executable && plan?.executable && plan.fingerprint) && stage !== 'committing';
  const canCommit = Boolean(approvalToken && acceptance?.accepted) && stage !== 'committing';

  async function handlePreview() {
    if (!canPreview) return;
    setStage('previewing'); setError(''); setPlan(null); setAcceptance(null); setApprovalToken('');
    try {
      const result = await client.preview(projectId, question.trim(), versionId);
      setPreview(result);
      if (!result.executable) { setStage('error'); setError(result.validation_errors.join('; ') || 'The proposal is not executable.'); return; }
      const nextPlan = await client.planPreview(projectId, result.proposal);
      setPlan(nextPlan);
      if (!nextPlan.executable) { setStage('error'); setError(nextPlan.validation_errors.join('; ') || 'The deterministic plan is not executable.'); return; }
      setStage('planned');
    } catch (caught) { setStage('error'); setError(toMessage(caught)); }
  }

  async function handleApproval() {
    if (!preview?.proposal || !canApprove) return;
    setStage('approval'); setError('');
    try {
      const tokenResponse = await client.issueApprovalToken(projectId, preview.proposal);
      setApprovalToken(tokenResponse.approval_token);
      const result = await client.acceptance(projectId, preview.proposal, tokenResponse.approval_token);
      setAcceptance(result);
      if (!result.accepted) { setStage('error'); setError(result.reasons.join('; ') || 'The proposal did not pass the acceptance gate.'); return; }
      setStage('accepted');
    } catch (caught) { setStage('error'); setError(toMessage(caught)); }
  }

  async function handleCommit() {
    if (!preview?.proposal || !canCommit) return;
    setStage('committing'); setError('');
    try { await client.commit(projectId, preview.proposal, approvalToken); setStage('committed'); await onCommitted?.(); }
    catch (caught) { setStage('error'); setError(toMessage(caught)); }
  }

  return (
    <section className="phase-card copilot-panel" aria-labelledby="copilot-title">
      <div className="copilot-header">
        <div><p className="eyebrow">COPILOT / EXECUTION-GROUNDED</p><h2 id="copilot-title">Ask the building brain</h2><p className="muted">AI proposes. Deterministic validation decides. Canonical state changes only after approval.</p></div>
        <span className={`copilot-stage ${stage}`}>{stage.replaceAll('_', ' ')}</span>
      </div>
      <div className="copilot-input-row">
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={4000} rows={4} placeholder="e.g. Increase the courtyard to 120 m² and explain what becomes stale." aria-label="Copilot request" disabled={stage === 'previewing' || stage === 'committing'} />
        <button className="btn primary" type="button" disabled={!canPreview} onClick={handlePreview}>{stage === 'previewing' ? 'Reasoning…' : 'Preview proposal'}</button>
      </div>
      {error && <div className="alert" role="alert">{error}</div>}
      {preview && <div className="copilot-result">
        <div className="copilot-summary"><div><p className="eyebrow">PROPOSAL</p><h3>{preview.proposal.summary}</h3><p>{preview.proposal.intent} · {Math.round(preview.proposal.confidence * 100)}% model confidence</p></div><span className={`requirement-state ${preview.executable ? 'confirmed' : 'rejected'}`}>{preview.executable ? 'Validated proposal' : 'Rejected'}</span></div>
        <div className="copilot-meta"><span>Revision <code>{revisionHash.slice(0, 16)}…</code></span><span>Commands <b>{preview.proposal.commands.length}</b></span><span>Evidence <b>{preview.proposal.evidence_ids.length}</b></span></div>
        {plan && <div className="copilot-plan"><div><p className="eyebrow">DETERMINISTIC PLAN</p><h3>{plan.execution_order.length} execution step{plan.execution_order.length === 1 ? '' : 's'}</h3><p>{plan.impact_groups.length ? `Affected: ${plan.impact_groups.join(', ')}` : 'No downstream impact groups.'}</p></div><code>{plan.fingerprint?.slice(0, 24)}…</code></div>}
        {preview.proposal.commands.length > 0 && <div className="copilot-commands">{preview.proposal.commands.map((command) => <article key={command.command_id}><b>{command.command_type}</b><span>{command.reason}</span></article>)}</div>}
        <div className="card-actions"><button className="btn outline" type="button" disabled={!canApprove} onClick={handleApproval}>{stage === 'approval' ? 'Checking…' : 'Approve proposal'}</button><button className="btn primary" type="button" disabled={!canCommit} onClick={handleCommit}>{stage === 'committing' ? 'Committing…' : stage === 'committed' ? 'Committed' : 'Commit canonical change'}</button>{acceptance && <span>{acceptance.accepted ? 'Acceptance gate passed.' : acceptance.reasons.join('; ')}</span>}</div>
      </div>}
      {stage === 'committed' && <div className="copilot-success">Canonical state updated. Affected artifacts have entered the deterministic regeneration boundary.</div>}
    </section>
  );
}

function toMessage(error: unknown): string {
  if (error instanceof CopilotApiError) return `${error.message} (HTTP ${error.status})`;
  if (error instanceof Error) return error.message;
  return 'Copilot request failed.';
}

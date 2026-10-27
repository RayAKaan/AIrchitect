import { useMemo, useState } from 'react';
import { createOpenCodeSession, sendOpenCodePrompt } from '../settings/openCodeClient';
import { loadAgentSettings } from '../settings/AgentSettings';
import type { ProductMode } from '../../state/productWorkspace';
import './UnifiedAgentBar.css';

type Props = { projectId: string; versionId: string; mode: ProductMode; context: string; onProposal?: (text: string) => void };

function sessionKey(projectId: string): string { return `airchitect:agent-session:${projectId}`; }

export default function UnifiedAgentBar({ projectId, versionId, mode, context, onProposal }: Props) {
  const [prompt, setPrompt] = useState(''); const [busy, setBusy] = useState(false); const [status, setStatus] = useState(''); const [response, setResponse] = useState('');
  const hasSession = useMemo(() => Boolean(sessionStorage.getItem(sessionKey(projectId))), [projectId]);

  async function submit() {
    const text = prompt.trim(); if (!text || busy) return;
    setBusy(true); setStatus('Thinking…');
    try {
      const settings = loadAgentSettings();
      let sessionId = sessionStorage.getItem(sessionKey(projectId));
      if (!sessionId) { const session = await createOpenCodeSession(settings.baseUrl, `AIrchitect · ${projectId}`, settings.username, settings.password); sessionId = session.id; sessionStorage.setItem(sessionKey(projectId), sessionId); }
      const result = await sendOpenCodePrompt(settings.baseUrl, sessionId, ['You are the AIrchitect reasoning agent.', `Project: ${projectId}`, `Version: ${versionId}`, `Current mode: ${mode}`, 'Treat canonical state as read-only unless an AIrchitect tool explicitly confirms a write. Return concise, actionable reasoning and clearly separate facts, assumptions, proposed changes and unknowns.', `Context:\n${context}`, `User request:\n${text}`].join('\n\n'), settings.username, settings.password);
      const serialized = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
      setResponse(serialized); setPrompt(''); setStatus('Response ready. No canonical mutation was performed.'); onProposal?.(serialized);
    } catch (cause) { setStatus(cause instanceof Error ? cause.message : 'The AI agent could not be reached.'); }
    finally { setBusy(false); }
  }

  return <section className="unified-agent-bar" aria-label="AIrchitect AI command bar"><div className="unified-agent-input"><span className="unified-agent-mark" aria-hidden="true">AI</span><input value={prompt} onChange={(event) => setPrompt(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submit(); } }} placeholder="Ask AIrchitect what to explore, explain or change…" aria-label="AIrchitect request" disabled={busy}/><button className="btn primary" onClick={() => void submit()} disabled={busy || !prompt.trim()}>{busy ? 'Thinking…' : 'Ask'}</button></div><div className="unified-agent-meta"><span>{hasSession ? 'Project agent session active' : 'Project agent session starts with your first request'}</span>{status && <span role="status">{status}</span>}</div>{response && <details className="unified-agent-response" open><summary>Latest agent response</summary><pre>{response}</pre></details>}</section>;
}

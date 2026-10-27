import { useState } from 'react';
import { createOpenCodeSession, sendOpenCodePrompt } from './openCodeClient';
import { loadAgentSettings } from './AgentSettings';
import './agentCommandBar.css';

type Props = { projectId: string; versionId: string; context?: string; placeholder?: string; onProposal?: (text: string) => void };

export default function AgentCommandBar({ projectId, versionId, context = '', placeholder = 'Ask AIrchitect to explore or change something…', onProposal }: Props) {
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');

  async function submit() {
    const text = prompt.trim();
    if (!text || busy) return;
    setBusy(true);
    setStatus('Thinking with OpenCode…');
    try {
      const settings = loadAgentSettings();
      const session = await createOpenCodeSession(settings.baseUrl, settings.username, settings.password, { title: `AIrchitect ${projectId}` });
      const response = await sendOpenCodePrompt(settings.baseUrl, settings.username, settings.password, session.id, [
        'You are operating as an AIrchitect architectural agent.',
        `Project: ${projectId}`,
        `Version: ${versionId}`,
        'Reason over the supplied context. Propose changes, but do not claim canonical mutation. Human approval is required before any write.',
        context ? `Canonical context:\n${context}` : '',
        `User request:\n${text}`,
      ].filter(Boolean).join('\n\n'));
      onProposal?.(response.text ?? response.content ?? '');
      setPrompt('');
      setStatus('Proposal ready for review.');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'OpenCode request failed.');
    } finally {
      setBusy(false);
    }
  }

  return <section className="agent-command-bar" aria-label="AIrchitect agent command bar">
    <div className="agent-command-input-wrap">
      <span className="agent-command-mark" aria-hidden="true">AI</span>
      <input value={prompt} onChange={(event) => setPrompt(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submit(); } }} placeholder={placeholder} disabled={busy} aria-label="Architectural agent request" />
      <button className="btn primary" onClick={() => void submit()} disabled={busy || !prompt.trim()}>{busy ? 'Thinking…' : 'Ask'}</button>
    </div>
    {status && <div className="agent-command-status" role="status">{status}</div>}
  </section>;
}

import { useEffect, useState } from 'react';
import { checkOpenCodeHealth, DEFAULT_OPENCODE_URL } from './openCodeClient';

const STORAGE_KEY = 'airchitect:agent-settings';

type AgentProvider = 'opencode';

type Settings = {
  provider: AgentProvider;
  baseUrl: string;
  username: string;
  password: string;
};

const DEFAULTS: Settings = { provider: 'opencode', baseUrl: DEFAULT_OPENCODE_URL, username: 'opencode', password: '' };

function readSettings(): Settings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<Settings>;
    return { ...DEFAULTS, ...parsed, provider: 'opencode' };
  } catch {
    return DEFAULTS;
  }
}

export function loadAgentSettings(): Settings {
  return readSettings();
}

export default function AgentSettings() {
  const [settings, setSettings] = useState<Settings>(readSettings);
  const [status, setStatus] = useState<'idle' | 'checking' | 'connected' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  }, [settings]);

  function update<K extends keyof Settings>(key: K, value: Settings[K]) {
    setSettings((current) => ({ ...current, [key]: value }));
    setSaved(false);
    setStatus('idle');
    setMessage('');
  }

  async function testConnection() {
    setStatus('checking');
    setMessage('');
    try {
      const health = await checkOpenCodeHealth(settings.baseUrl, settings.username, settings.password);
      setStatus('connected');
      setMessage(`OpenCode ${health.version} is reachable.`);
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Could not connect to OpenCode.');
    }
  }

  function save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    setSaved(true);
  }

  return (
    <section className="settings-panel">
      <div className="settings-header">
        <div>
          <div className="eyebrow">AI / AGENT</div>
          <h2>Agent provider</h2>
          <p className="muted">Choose the agent that reasons over architectural work. OpenCode is the first supported provider.</p>
        </div>
        <span className="settings-badge">LOCAL CONFIG</span>
      </div>

      <div className="settings-card">
        <div className="settings-card-head">
          <div>
            <h3>OpenCode</h3>
            <p className="muted">Connect AIrchitect to an OpenCode server running on this machine or another trusted host.</p>
          </div>
          <label className="settings-radio"><input type="radio" checked={settings.provider === 'opencode'} onChange={() => update('provider', 'opencode')} /> Active</label>
        </div>

        <div className="settings-grid">
          <label>Server URL<input value={settings.baseUrl} onChange={(e) => update('baseUrl', e.target.value)} placeholder="http://127.0.0.1:4096" /></label>
          <label>Server username<input value={settings.username} onChange={(e) => update('username', e.target.value)} placeholder="opencode" autoComplete="username" /></label>
          <label className="settings-wide">Server password<input type="password" value={settings.password} onChange={(e) => update('password', e.target.value)} placeholder="Optional OPENCODE_SERVER_PASSWORD" autoComplete="current-password" /></label>
        </div>

        <div className="settings-actions">
          <button className="btn outline" onClick={testConnection} disabled={status === 'checking'}>{status === 'checking' ? 'Testing…' : 'Test connection'}</button>
          <button className="btn primary" onClick={save}>Save settings</button>
          {saved && <span className="settings-saved">Saved</span>}
        </div>

        {status !== 'idle' && <div className={`settings-status ${status}`} role="status">{status === 'connected' ? '● Connected · ' : status === 'error' ? '● Connection failed · ' : ''}{message}</div>}
      </div>

      <div className="settings-card settings-note">
        <h3>Credentials stay with OpenCode</h3>
        <p>AIrchitect does not store OpenAI, Anthropic, OpenRouter, or other model-provider API keys. Configure provider authentication in OpenCode; AIrchitect only connects to the OpenCode server.</p>
        <p>Jev is intentionally not exposed as a provider yet. Additional agent providers can be added later without changing the architectural workspace contract.</p>
        <code>opencode serve --port 4096 --cors http://localhost:5173</code>
      </div>
    </section>
  );
}

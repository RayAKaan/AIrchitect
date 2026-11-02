import { useEffect, useMemo, useState } from 'react';
import {
  checkOpenCodeHealth, DEFAULT_OPENCODE_URL, listOpenCodeProviders, registerOpenCodeMcpServer, resolveMcpEndpoint, setOpenCodeProviderKey,
  type OpenCodeProvider, type OpenCodeProviderCatalog,
} from './openCodeClient';
import './agentSettings.css';

const STORAGE_KEY = 'airchitect:agent-settings';
const SECRET_STORAGE_KEY = 'airchitect:agent-session-secret';

export type AgentSettingsState = { baseUrl: string; username: string; password: string; providerId: string; modelId: string };
const DEFAULTS: AgentSettingsState = { baseUrl: DEFAULT_OPENCODE_URL, username: 'opencode', password: '', providerId: '', modelId: '' };

function readSettings(): AgentSettingsState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const password = sessionStorage.getItem(SECRET_STORAGE_KEY) || '';
    return raw ? { ...DEFAULTS, ...(JSON.parse(raw) as Partial<AgentSettingsState>), password } : { ...DEFAULTS, password };
  } catch { return { ...DEFAULTS, password: '' }; }
}

export function loadAgentSettings(): AgentSettingsState { return readSettings(); }

function providerModels(provider?: OpenCodeProvider) {
  return Object.values(provider?.models ?? {}).sort((a, b) => (a.name || a.id).localeCompare(b.name || b.id));
}

export default function AgentSettings({ apiBaseUrl, token }: { apiBaseUrl: string; token: string }) {
  const [settings, setSettings] = useState<AgentSettingsState>(readSettings);
  const [catalog, setCatalog] = useState<OpenCodeProviderCatalog | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [status, setStatus] = useState<'idle' | 'checking' | 'connected' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [saved, setSaved] = useState(false);
  const [keyBusy, setKeyBusy] = useState(false);

  useEffect(() => {
    const { password, ...safeSettings } = settings;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(safeSettings));
    if (password) sessionStorage.setItem(SECRET_STORAGE_KEY, password);
    else sessionStorage.removeItem(SECRET_STORAGE_KEY);
  }, [settings]);

  function update<K extends keyof AgentSettingsState>(key: K, value: AgentSettingsState[K]) {
    setSettings(current => ({ ...current, [key]: value }));
    setSaved(false);
    if (['baseUrl', 'username', 'password'].includes(key)) { setStatus('idle'); setCatalog(null); setMessage(''); }
  }

  async function testConnection() {
    setStatus('checking'); setMessage('');
    try {
      const health = await checkOpenCodeHealth(settings.baseUrl, settings.username, settings.password);
      const providers = await listOpenCodeProviders(settings.baseUrl, settings.username, settings.password);
      await registerOpenCodeMcpServer(settings.baseUrl, resolveMcpEndpoint(apiBaseUrl), token, settings.username, settings.password);
      setCatalog(providers); setStatus('connected');
      setMessage(`OpenCode ${health.version} is connected. ${providers.connected.length} provider(s) configured.`);
      if (!settings.providerId && providers.connected[0]) {
        const provider = providers.all.find(item => item.id === providers.connected[0]);
        const firstModel = providerModels(provider)[0];
        update('providerId', provider?.id || '');
        update('modelId', providers.default[providers.connected[0]] || firstModel?.id || '');
      }
    } catch (error) { setStatus('error'); setMessage(error instanceof Error ? error.message : 'Could not connect to OpenCode.'); }
  }

  async function saveProviderKey() {
    if (!settings.providerId || !apiKey.trim()) return;
    setKeyBusy(true); setMessage('');
    try {
      await setOpenCodeProviderKey(settings.baseUrl, settings.providerId, apiKey.trim(), settings.username, settings.password);
      setApiKey('');
      const providers = await listOpenCodeProviders(settings.baseUrl, settings.username, settings.password);
      setCatalog(providers); setStatus('connected');
      setMessage('Provider credential saved by OpenCode on this device. AIrchitect did not store the key.');
    } catch (error) { setStatus('error'); setMessage(error instanceof Error ? error.message : 'Could not save provider credential.'); }
    finally { setKeyBusy(false); }
  }

  function save() {
    const { password, ...safeSettings } = settings;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(safeSettings));
    if (password) sessionStorage.setItem(SECRET_STORAGE_KEY, password);
    setSaved(true);
  }

  const mcpUrl = useMemo(() => resolveMcpEndpoint(apiBaseUrl), [apiBaseUrl]);
  const setupCommand = `node scripts/agent-runtime.mjs setup --origin ${window.location.origin}`;
  const selectedProvider = catalog?.all.find(provider => provider.id === settings.providerId);
  const models = providerModels(selectedProvider);
  const isConnected = Boolean(catalog?.connected.includes(settings.providerId));

  return <section className="settings-panel">
    <div className="settings-header"><div><div className="eyebrow">AI / AGENT</div><h2>Agent provider</h2><p className="muted">OpenCode is the default agent runtime. Choose any provider and model supported by your OpenCode installation.</p></div><span className="settings-badge">LOCAL AGENT</span></div>
    <div className="settings-card">
      <div className="settings-card-head"><div><h3>OpenCode runtime</h3><p className="muted">Connect to the local OpenCode server installed on this device.</p></div><span className="settings-radio">{status === 'connected' ? '● Connected' : '○ Not connected'}</span></div>
      <div className="settings-grid">
        <label>Server URL<input value={settings.baseUrl} onChange={event => update('baseUrl', event.target.value)} placeholder="http://127.0.0.1:4096" /></label>
        <label>Server username<input value={settings.username} onChange={event => update('username', event.target.value)} placeholder="opencode" autoComplete="username" /></label>
        <label className="settings-wide">Server password<input type="password" value={settings.password} onChange={event => update('password', event.target.value)} placeholder="Password printed by the runtime setup" autoComplete="current-password" /></label>
      </div>
      <div className="settings-actions"><button className="btn outline" onClick={() => void testConnection()} disabled={status === 'checking'}>{status === 'checking' ? 'Testing…' : 'Connect and discover providers'}</button><button className="btn primary" onClick={save}>Save settings</button>{saved && <span className="settings-saved">Saved</span>}</div>
      {message && <div className={`settings-status ${status === 'error' ? 'error' : 'connected'}`} role="status">{message}</div>}
    </div>
    {catalog && <div className="settings-card">
      <h3>Model provider and default model</h3><p className="muted">Credentials are stored by OpenCode in its local credential store, not in AIrchitect browser storage or database.</p>
      <div className="settings-grid">
        <label>Provider<select value={settings.providerId} onChange={event => {
          const providerId = event.target.value; const provider = catalog.all.find(item => item.id === providerId); const firstModel = providerModels(provider)[0];
          update('providerId', providerId); update('modelId', catalog.default[providerId] || firstModel?.id || '');
        }}><option value="">Select a provider</option>{catalog.all.map(provider => <option key={provider.id} value={provider.id}>{provider.name}{catalog.connected.includes(provider.id) ? ' · connected' : ''}</option>)}</select></label>
        <label>Model<select value={settings.modelId} onChange={event => update('modelId', event.target.value)} disabled={!models.length}><option value="">Select a model</option>{models.map(model => <option key={model.id} value={model.id}>{model.name || model.id}</option>)}</select></label>
        <label className="settings-wide">Provider API key<input type="password" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder={settings.providerId ? `API key for ${selectedProvider?.name || settings.providerId}` : 'Select a provider first'} autoComplete="new-password" /></label>
      </div>
      <div className="settings-actions"><button className="btn outline" onClick={() => void saveProviderKey()} disabled={!settings.providerId || !apiKey.trim() || keyBusy}>{keyBusy ? 'Saving credential…' : 'Save provider credential'}</button><span className="settings-saved">{isConnected ? 'Provider credential available' : 'Provider not yet connected'}</span></div>
      <p className="muted">Selected model: {settings.providerId && settings.modelId ? `${settings.providerId}/${settings.modelId}` : 'OpenCode default'}. Save settings to use it for new agent requests.</p>
    </div>}
    <div className="settings-card settings-note"><h3>Install the local agent</h3><p>A browser cannot install native software without your approval. Run this one-time setup command from the AIrchitect repository on your computer. It installs the pinned OpenCode CLI and starts a loopback-only server.</p><code>{setupCommand}</code><p><strong>Protected MCP endpoint</strong></p><code>{mcpUrl}</code><p>Connecting registers the authenticated AIrchitect MCP server with your loopback OpenCode runtime. Session credentials are refreshed on every agent request and are never stored in browser localStorage. MCP tools expose project, site, design and artifact context plus deterministic previews; canonical changes remain behind AIrchitect's approval and command-validation boundary.</p></div>
  </section>;
}

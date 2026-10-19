import { useEffect, useMemo, useState } from 'react';

type Provider = { provider_id: string; capability: string; health_status: string; coverage: Record<string, unknown>; terms: { version: string; license: string | null; attribution_required: boolean; commercial_use: string; caching_allowed: boolean; source_url: string | null; review_due_at: string | null } | null };
type Result = { feature_count: number; dataset_version: string | null; status: string };

const HEALTHY = new Set(['healthy', 'ok', 'available']);

export default function SiteProviderPanel({ api, token, siteId, revision, onFetched }: { api: string; token: string; siteId: string; revision: string; onFetched: () => void }) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selected, setSelected] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${api}/sites/providers`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async response => {
        if (!response.ok) throw new Error('Could not load provider catalog');
        return response.json() as Promise<Provider[]>;
      })
      .then(data => {
        if (cancelled) return;
        setProviders(data);
        const first = data.find(item => item.capability === 'context' && item.terms?.commercial_use !== 'UNKNOWN' && item.terms?.caching_allowed && HEALTHY.has(item.health_status.toLowerCase()));
        setSelected(first?.provider_id ?? '');
      })
      .catch(cause => { if (!cancelled) setError(cause instanceof Error ? cause.message : 'Could not load provider catalog'); });
    return () => { cancelled = true; };
  }, [api, token]);

  const contextProviders = useMemo(() => providers.filter(item => item.capability === 'context'), [providers]);
  const active = contextProviders.find(item => item.provider_id === selected) ?? null;
  const termsApproved = Boolean(active?.terms && active.terms.commercial_use !== 'UNKNOWN' && active.terms.caching_allowed);
  const providerHealthy = Boolean(active && HEALTHY.has(active.health_status.toLowerCase()));
  const canFetch = Boolean(active && termsApproved && providerHealthy && !busy);

  async function fetchContext() {
    if (!active || !canFetch) return;
    setBusy(true); setError(''); setResult(null);
    try {
      const response = await fetch(`${api}/sites/${siteId}/revisions/${revision}/context/${encodeURIComponent(active.provider_id)}`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Context fetch failed');
      setResult(data); onFetched();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Context fetch failed'); }
    finally { setBusy(false); }
  }

  return <section className="site-provider-panel phase-card" aria-label="Site context providers">
    <div className="section-head"><div><p className="eyebrow">PROVIDER CONTEXT</p><h2>Evidence-backed site context</h2><p className="muted">Only server-registered providers with reviewed terms and a healthy runtime can persist context into the canonical site workflow.</p></div></div>
    {contextProviders.length === 0 ? <div className="empty-state compact"><div><h3>No context provider configured</h3><p>Context remains UNKNOWN until an approved provider is registered.</p></div></div> : <div className="provider-grid">
      <label className="provider-select">Provider<select aria-label="Context provider" value={selected} onChange={event => { setSelected(event.target.value); setResult(null); }}>{contextProviders.map(provider => <option key={provider.provider_id} value={provider.provider_id}>{provider.provider_id}</option>)}</select></label>
      {active && <div className="provider-terms"><strong>{active.provider_id}</strong><span>Health: {active.health_status}</span><span>Terms: {active.terms?.version ?? 'unregistered'}</span><span>License: {active.terms?.license ?? 'UNKNOWN'}</span><span>Commercial: {active.terms?.commercial_use ?? 'UNKNOWN'}</span><span>Persistence: {active.terms?.caching_allowed ? 'allowed' : 'blocked'}</span>{active.terms?.attribution_required && <span>Attribution: required</span>}{active.terms?.source_url && <a href={active.terms.source_url} target="_blank" rel="noreferrer">Review provider terms</a>}</div>}
      {!providerHealthy && active && <div className="alert" role="status">Provider runtime is not healthy. Fetching is disabled until the server reports availability.</div>}
      {active && !termsApproved && <div className="alert" role="status">Provider terms do not explicitly permit the requested persistence/commercial use. Context remains unpersisted.</div>}
      <button className="btn primary" disabled={!canFetch} onClick={fetchContext}>{busy ? 'Fetching context…' : 'Fetch site context'}</button>
    </div>}
    {error && <div className="alert" role="alert">{error}</div>}
    {result && <div className="provider-result" role="status">Loaded {result.feature_count} persisted features · dataset {result.dataset_version ?? 'unknown'} · {result.status}</div>}
  </section>;
}

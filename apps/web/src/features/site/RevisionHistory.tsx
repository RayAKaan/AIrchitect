import { useEffect, useState } from 'react';

type Revision = { id: string; revision: number; content_hash: string; parent_revision_id: string | null; area_m2: number; perimeter_m: number; created_at: string };
type Freshness = { artifacts: { id: string; layer_type: string; site_revision_id: string; status: string; source_revision_hash: string | null }[]; evidence: { id: string; site_revision_id: string; claim_type: string; status: string }[] };
export default function RevisionHistory({ api, token, siteId, currentRevision }: { api: string; token: string; siteId: string; currentRevision: string }) {
  const [items, setItems] = useState<Revision[]>([]); const [freshness, setFreshness] = useState<Freshness | null>(null);
  useEffect(() => { let cancelled = false; Promise.all([
    fetch(`${api}/sites/${siteId}/revisions`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.ok ? r.json() : Promise.reject(new Error('Could not load revisions'))),
    fetch(`${api}/sites/${siteId}/freshness`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.ok ? r.json() : Promise.reject(new Error('Could not load freshness'))),
  ]).then(([revisions, state]) => { if (!cancelled) { setItems(revisions); setFreshness(state); } }).catch(() => undefined); return () => { cancelled = true; }; }, [api, token, siteId, currentRevision]);
  const staleArtifacts = freshness?.artifacts.filter(item => item.status === 'STALE').length ?? 0;
  return <section className="revision-history" aria-label="Site revision history"><div className="section-head"><div><p className="eyebrow">HISTORY / DEPENDENCIES</p><h2>Site revisions</h2></div><span className="muted">{items.length} revisions</span></div>{staleArtifacts > 0 && <div className="alert" role="status"><strong>{staleArtifacts} derived artifact{staleArtifacts === 1 ? '' : 's'} stale.</strong> They belong to an older site revision and must not be treated as current.</div>}<div className="revision-list">{items.map(item => <article className={`revision-row ${item.id === currentRevision ? 'current' : ''}`} key={item.id}><div><strong>Revision {item.revision}</strong>{item.id === currentRevision && <span className="revision-current">CURRENT</span>}<p><code>{item.content_hash.slice(0, 16)}…</code></p></div><div><span>{item.area_m2.toFixed(1)} m²</span><small>{new Date(item.created_at).toLocaleString()}</small></div></article>)}</div></section>;
}

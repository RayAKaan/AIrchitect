import { useEffect, useState } from 'react';

type Revision = { id: string; revision: number; content_hash: string; parent_revision_id: string | null; area_m2: number; perimeter_m: number; created_at: string };
export default function RevisionHistory({ api, token, siteId, currentRevision }: { api: string; token: string; siteId: string; currentRevision: string }) {
  const [items, setItems] = useState<Revision[]>([]);
  useEffect(() => { let cancelled = false; fetch(`${api}/sites/${siteId}/revisions`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.ok ? r.json() : Promise.reject(new Error('Could not load revisions'))).then(data => { if (!cancelled) setItems(data); }).catch(() => undefined); return () => { cancelled = true; }; }, [api, token, siteId]);
  return <section className="revision-history" aria-label="Site revision history"><div className="section-head"><div><p className="eyebrow">HISTORY</p><h2>Site revisions</h2></div><span className="muted">{items.length} revisions</span></div><div className="revision-list">{items.map(item => <article className={`revision-row ${item.id === currentRevision ? 'current' : ''}`} key={item.id}><div><strong>Revision {item.revision}</strong>{item.id === currentRevision && <span className="revision-current">CURRENT</span>}<p><code>{item.content_hash.slice(0, 16)}…</code></p></div><div><span>{item.area_m2.toFixed(1)} m²</span><small>{new Date(item.created_at).toLocaleString()}</small></div></article>)}</div></section>;
}

import { useMemo, useState } from 'react';
import '../../foundation.css';

type Item = { id: string; title: string; kind: string; status: string };

export default function BoardComposer({ projectName }: { projectName: string }) {
  const [items, setItems] = useState<Item[]>([
    { id: 'title', title: projectName, kind: 'Title', status: 'SUPPORTED' },
    { id: 'site', title: 'Site boundary', kind: 'Map', status: 'CANONICAL' },
    { id: 'analysis', title: 'Site analysis', kind: 'Metrics', status: 'SUPPORTED' },
    { id: 'evidence', title: 'Evidence / provenance', kind: 'Evidence', status: 'SUPPORTED' },
  ]);
  const [staleAcknowledged, setStaleAcknowledged] = useState(false);
  const canExport = useMemo(() => items.length > 0 && !items.some(item => item.status === 'STALE') || staleAcknowledged, [items, staleAcknowledged]);
  function addDiagram() { setItems(current => [...current, { id: `diagram-${current.length + 1}`, title: `Diagram ${current.length - 3}`, kind: 'Diagram', status: 'SUPPORTED' }]); }
  return <section className="board-composer phase-card" aria-label="Board composer"><div className="section-head"><div><p className="eyebrow">BOARD COMPOSER</p><h2>Site analysis board</h2><p className="muted">A1 portrait · deterministic placement · provenance-aware content.</p></div><div className="card-actions"><button className="btn outline" onClick={addDiagram}>Add diagram</button><button className="btn primary" disabled={!canExport} onClick={() => window.print()}>Print / PDF</button></div></div><div className="board-stage"><div className="board-sheet" role="document" aria-label="A1 board preview">{items.map((item, index) => <article className={`board-item board-${item.kind.toLowerCase()}`} key={item.id}><span className="board-item-kind">{item.kind}</span><h3>{item.title}</h3><p>{item.status === 'CANONICAL' ? 'Canonical site revision' : item.status === 'STALE' ? 'STALE DATA' : 'Evidence-bound derived content'}</p><small>Item {index + 1} · source-aware</small></article>)}<footer>PRELIMINARY · Verify against canonical revision before professional use</footer></div></div>{items.some(item => item.status === 'STALE') && <label className="stale-ack"><input type="checkbox" checked={staleAcknowledged} onChange={e => setStaleAcknowledged(e.target.checked)}/> I acknowledge that this board contains stale data.</label>}</section>;
}

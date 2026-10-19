import { useEffect, useMemo, useState } from 'react';
import '../../foundation.css';
import './board-composer.css';

type Item = { id: string; title: string; kind: string; status: string; x: number; y: number; w: number; h: number };
type Format = 'A1' | 'A2' | 'A3' | '16:9';
const FORMATS: Record<Format, { width: number; height: number; label: string }> = { A1: { width: 794, height: 1123, label: 'A1 portrait' }, A2: { width: 600, height: 848, label: 'A2 portrait' }, A3: { width: 420, height: 594, label: 'A3 portrait' }, '16:9': { width: 960, height: 540, label: '16:9 landscape' } };

function initialItems(projectName: string): Item[] { return [
  { id: 'title', title: projectName, kind: 'Title', status: 'SUPPORTED', x: 0, y: 0, w: 2, h: 1 },
  { id: 'site', title: 'Site boundary', kind: 'Map', status: 'CANONICAL', x: 0, y: 1, w: 1, h: 2 },
  { id: 'analysis', title: 'Site analysis', kind: 'Metrics', status: 'SUPPORTED', x: 1, y: 1, w: 1, h: 1 },
  { id: 'evidence', title: 'Evidence / provenance', kind: 'Evidence', status: 'SUPPORTED', x: 1, y: 2, w: 1, h: 1 },
]; }

export default function BoardComposer({ projectName }: { projectName: string }) {
  const storageKey = `airchitect.board.${projectName}`;
  const [format, setFormat] = useState<Format>('A1');
  const [items, setItems] = useState<Item[]>(() => { try { const saved = JSON.parse(localStorage.getItem(storageKey) || 'null'); return Array.isArray(saved?.items) ? saved.items : initialItems(projectName); } catch { return initialItems(projectName); } });
  const [selected, setSelected] = useState('title'); const [staleAcknowledged, setStaleAcknowledged] = useState(false); const [saved, setSaved] = useState(false);
  const canExport = useMemo(() => !items.some(item => item.status === 'STALE') || staleAcknowledged, [items, staleAcknowledged]);
  useEffect(() => { const raw = localStorage.getItem(storageKey); try { const parsed = raw ? JSON.parse(raw) : null; if (parsed?.format && parsed.format in FORMATS) setFormat(parsed.format); } catch { /* ignore corrupt local draft */ } }, [storageKey]);
  function saveLayout() { localStorage.setItem(storageKey, JSON.stringify({ format, items, savedAt: new Date().toISOString() })); setSaved(true); window.setTimeout(() => setSaved(false), 1500); }
  function addDiagram() { const index = items.filter(item => item.kind === 'Diagram').length + 1; setItems(current => [...current, { id: `diagram-${index}`, title: `Diagram ${index}`, kind: 'Diagram', status: 'SUPPORTED', x: index % 2, y: 3 + Math.floor(index / 2), w: 1, h: 1 }]); }
  function nudge(deltaX: number, deltaY: number) { setItems(current => current.map(item => item.id === selected ? { ...item, x: Math.max(0, item.x + deltaX), y: Math.max(0, item.y + deltaY) } : item)); }
  return <section className="board-composer phase-card" aria-label="Board composer"><div className="section-head"><div><p className="eyebrow">BOARD COMPOSER</p><h2>Site analysis board</h2><p className="muted">{FORMATS[format].label} · source-aware layout · deterministic content.</p></div><div className="card-actions"><label className="board-format">Sheet <select value={format} onChange={event => setFormat(event.target.value as Format)}>{Object.entries(FORMATS).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</select></label><button className="btn outline" onClick={addDiagram}>Add diagram</button><button className="btn outline" onClick={saveLayout}>{saved ? 'Saved' : 'Save layout'}</button><button className="btn primary" disabled={!canExport} onClick={() => window.print()}>Print / PDF</button></div></div>
    <div className="board-controls" aria-label="Selected item controls"><span>Selected: <strong>{items.find(item => item.id === selected)?.title ?? 'None'}</strong></span><button onClick={() => nudge(-1, 0)} disabled={!selected}>←</button><button onClick={() => nudge(1, 0)} disabled={!selected}>→</button><button onClick={() => nudge(0, -1)} disabled={!selected}>↑</button><button onClick={() => nudge(0, 1)} disabled={!selected}>↓</button></div>
    <div className="board-stage"><div className={`board-sheet board-format-${format.replace(':', '-')}`} style={{ width: FORMATS[format].width, minHeight: FORMATS[format].height }} role="document" aria-label={`${FORMATS[format].label} board preview`} onKeyDown={event => { if (event.key === 'ArrowLeft') nudge(-1, 0); if (event.key === 'ArrowRight') nudge(1, 0); if (event.key === 'ArrowUp') nudge(0, -1); if (event.key === 'ArrowDown') nudge(0, 1); }}>{items.map((item, index) => <article className={`board-item board-${item.kind.toLowerCase()} ${item.id === selected ? 'selected' : ''}`} style={{ gridColumn: `${item.x + 1} / span ${item.w}`, gridRow: `${item.y + 1} / span ${item.h}` }} tabIndex={0} key={item.id} onClick={() => setSelected(item.id)} onFocus={() => setSelected(item.id)}><span className="board-item-kind">{item.kind}</span><h3>{item.title}</h3><p>{item.status === 'CANONICAL' ? 'Canonical site revision' : item.status === 'STALE' ? 'STALE DATA' : 'Evidence-bound derived content'}</p><small>Item {index + 1} · source-aware</small></article>)}<footer>PRELIMINARY · Verify against canonical revision before professional use · Evidence appendix included</footer></div></div>{items.some(item => item.status === 'STALE') && <label className="stale-ack"><input type="checkbox" checked={staleAcknowledged} onChange={e => setStaleAcknowledged(e.target.checked)}/> I acknowledge that this board contains stale data.</label>}</section>;
}

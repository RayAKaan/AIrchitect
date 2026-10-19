import { useMemo, useState } from 'react';
import './site-workspace.css';

type Point = [number, number];
type SiteRevision = { site_id: string; site_revision_id: string; revision: number; boundary: { type: 'Polygon'; coordinates: Point[][] }; boundary_crs: string; calculation_crs: string; area_m2: number; perimeter_m: number; content_hash: string; parent_revision_id: string | null };

const DEFAULT_POINTS: Point[] = [[80, 70], [420, 70], [470, 300], [220, 390], [80, 300]];

function toGeoJSON(points: Point[]) {
  const coordinates = points.map(([x, y]) => [77.58 + x / 100000, 12.94 + y / 100000]);
  coordinates.push(coordinates[0]);
  return { type: 'Polygon', coordinates: [coordinates] };
}

export default function SiteWorkspace({ api, token, project }: { api: string; token: string; project: { id: string; name: string }; }) {
  const [points, setPoints] = useState<Point[]>(DEFAULT_POINTS);
  const [revision, setRevision] = useState<SiteRevision | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const polygon = useMemo(() => points.map(([x, y]) => `${x},${y}`).join(' '), [points]);

  async function commitBoundary() {
    setBusy(true); setError('');
    try {
      const response = await fetch(`${api}/projects/${project.id}/sites`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ command_id: crypto.randomUUID(), idempotency_key: crypto.randomUUID(), boundary: toGeoJSON(points), reason: 'Set site boundary from workspace' }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error?.message || 'Could not set site boundary');
      setRevision(data); setSelected(null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not set site boundary'); }
    finally { setBusy(false); }
  }

  function movePoint(index: number, event: React.PointerEvent<SVGCircleElement>) {
    const svg = event.currentTarget.ownerSVGElement;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const next: Point = [Math.max(30, Math.min(570, event.clientX - rect.left)), Math.max(30, Math.min(430, event.clientY - rect.top))];
    setPoints(current => current.map((point, currentIndex) => currentIndex === index ? next : point));
  }

  return <section className="site-workspace" aria-label="Site workspace">
    <header className="site-workspace-header"><div><p className="eyebrow">SITE / WORLD MODEL</p><h1>{project.name}</h1><p className="muted">Draw a boundary in the workspace. Canonical validation remains server-authoritative.</p></div><button className="btn primary" disabled={busy} onClick={commitBoundary}>{busy ? 'Validating…' : 'Set site boundary'}</button></header>
    {error && <div className="alert" role="alert">{error}</div>}
    <div className="site-workspace-grid">
      <article className="site-canvas-card"><div className="site-toolbar"><span>Boundary editor</span><span>WGS84 / EPSG:4326 input</span></div><svg viewBox="0 0 600 460" className="site-canvas" role="img" aria-label="Editable site boundary"><rect x="0" y="0" width="600" height="460" fill="transparent" stroke="currentColor" strokeOpacity=".15"/><polygon points={polygon} fill="currentColor" fillOpacity=".08" stroke="currentColor" strokeWidth="2"/>{points.map(([x, y], index) => <circle key={index} cx={x} cy={y} r={selected === index ? 9 : 7} tabIndex={0} aria-label={`Boundary point ${index + 1}`} onClick={() => setSelected(index)} onPointerMove={event => { if (event.buttons === 1) movePoint(index, event); }} onKeyDown={event => { if (event.key === 'ArrowLeft') setPoints(current => current.map((point, i) => i === index ? [point[0] - 2, point[1]] : point)); if (event.key === 'ArrowRight') setPoints(current => current.map((point, i) => i === index ? [point[0] + 2, point[1]] : point)); }}/>)}</svg><p className="site-help">Drag a vertex or select it and use arrow keys. The backend validates closure, topology, area and calculation CRS before creating a canonical revision.</p></article>
      <aside className="site-inspector"><p className="eyebrow">CANONICAL SITE</p><dl><div><dt>Status</dt><dd>{revision ? 'Revision created' : 'Draft boundary'}</dd></div><div><dt>Revision</dt><dd>{revision?.revision ?? '—'}</dd></div><div><dt>Area</dt><dd>{revision ? `${revision.area_m2.toFixed(1)} m²` : 'Pending validation'}</dd></div><div><dt>Perimeter</dt><dd>{revision ? `${revision.perimeter_m.toFixed(1)} m` : 'Pending validation'}</dd></div><div><dt>Calculation CRS</dt><dd>{revision?.calculation_crs ?? 'Local metric projection'}</dd></div><div><dt>Hash</dt><dd><code>{revision?.content_hash?.slice(0, 16) ?? '—'}{revision ? '…' : ''}</code></dd></div></dl>{revision && <div className="site-success">Canonical revision {revision.revision} is persisted. Downstream site analysis can now depend on this revision hash.</div>}</aside>
    </div>
  </section>;
}

import { useEffect, useMemo, useState } from 'react';
import './site-workspace.css';
import DiagramStudio from './DiagramStudio';
import EvidencePanel from './EvidencePanel';
import SiteOnboarding from './SiteOnboarding';
import RevisionHistory from './RevisionHistory';
import SiteMapSurface from './SiteMapSurface';
import SiteProviderPanel from './SiteProviderPanel';

type Point = [number, number];
type SiteRevision = { site_id: string; site_revision_id: string; revision: number; boundary: { type: 'Polygon'; coordinates: Point[][] }; boundary_crs: string; calculation_crs: string; area_m2: number; perimeter_m: number; content_hash: string; parent_revision_id: string | null };
type SiteLayer = { id: string; layer_type: string; provider: string | null; dataset_version: string | null; status: string; created_at: string; payload: Record<string, unknown> };
const DEFAULT_POINTS: Point[] = [[77.58, 12.94], [77.586, 12.94], [77.587, 12.944], [77.582, 12.947], [77.578, 12.944]];
const LAYER_LABELS: Record<string, string> = { CONTEXT: 'Context', ANALYSIS: 'Analysis', 'DIAGRAM:figure_ground': 'Figure-ground', 'DIAGRAM:movement': 'Movement', 'DIAGRAM:land_use': 'Land use', 'DIAGRAM:green_water': 'Green / water', 'DIAGRAM:solar': 'Solar' };

export default function SiteWorkspace({ api, token, project }: { api: string; token: string; project: { id: string; name: string } }) {
  const [points, setPoints] = useState<Point[]>(DEFAULT_POINTS); const [revision, setRevision] = useState<SiteRevision | null>(null); const [layers, setLayers] = useState<SiteLayer[]>([]); const [visibleLayers, setVisibleLayers] = useState<Record<string, boolean>>({}); const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [layerRefresh, setLayerRefresh] = useState(0);
  useEffect(() => { if (!revision) return; let cancelled = false; fetch(`${api}/sites/${revision.site_id}/revisions/${revision.site_revision_id}/layers`, { headers: { Authorization: `Bearer ${token}` } }).then(async response => { if (!response.ok) throw new Error('Could not load site layers'); return response.json() as Promise<SiteLayer[]>; }).then(data => { if (!cancelled) { setLayers(data); setVisibleLayers(Object.fromEntries(data.map(layer => [layer.layer_type, true]))); } }).catch(cause => { if (!cancelled) setError(cause instanceof Error ? cause.message : 'Could not load site layers'); }); return () => { cancelled = true; }; }, [api, token, revision, layerRefresh]);
  async function commitBoundary() { setBusy(true); setError(''); try { const coordinates = [...points, points[0]]; const response = await fetch(`${api}/projects/${project.id}/sites`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ command_id: crypto.randomUUID(), idempotency_key: crypto.randomUUID(), boundary: { type: 'Polygon', coordinates: [coordinates] }, reason: 'Set site boundary from workspace' }) }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || data.error?.message || 'Could not set site boundary'); setRevision(data); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not set site boundary'); } finally { setBusy(false); } }
  const layerControls = useMemo(() => layers.map(layer => ({ label: LAYER_LABELS[layer.layer_type] ?? layer.layer_type, visible: visibleLayers[layer.layer_type] ?? true })), [layers, visibleLayers]);
  return <section className="site-workspace" aria-label="Site workspace">
    <SiteOnboarding />
    <header className="site-workspace-header"><div><p className="eyebrow">SITE / WORLD MODEL</p><h1>{project.name}</h1><p className="muted">Define a canonical site boundary. Geometry is editable locally; validation and revision creation remain server-authoritative.</p></div><button className="btn primary" disabled={busy} onClick={commitBoundary}>{busy ? 'Validating…' : 'Set site boundary'}</button></header>
    {error && <div className="alert" role="alert">{error}</div>}
    <div className="site-workspace-grid">
      <article className="site-canvas-card"><div className="site-toolbar"><span>Site map</span><span>{revision ? `Revision ${revision.revision}` : 'Draft boundary'}</span></div><SiteMapSurface points={points} onChange={setPoints} layers={layerControls} onToggleLayer={index => { const layer = layers[index]; if (!layer) return; setVisibleLayers(current => ({ ...current, [layer.layer_type]: !(current[layer.layer_type] ?? true) })); }} /><p className="site-help">Edit vertices directly on the site surface or with the keyboard. The editor stores WGS84 coordinates; the backend validates topology, area, closure and the calculation CRS before persistence.</p></article>
      <aside className="site-inspector"><p className="eyebrow">CANONICAL SITE</p><dl><div><dt>Status</dt><dd>{revision ? 'Revision created' : 'Draft boundary'}</dd></div><div><dt>Revision</dt><dd>{revision?.revision ?? '—'}</dd></div><div><dt>Area</dt><dd>{revision ? `${revision.area_m2.toFixed(1)} m²` : 'Pending validation'}</dd></div><div><dt>Perimeter</dt><dd>{revision ? `${revision.perimeter_m.toFixed(1)} m` : 'Pending validation'}</dd></div><div><dt>Boundary CRS</dt><dd>{revision?.boundary_crs ?? 'EPSG:4326'}</dd></div><div><dt>Calculation CRS</dt><dd>{revision?.calculation_crs ?? 'Local metric projection'}</dd></div><div><dt>Hash</dt><dd><code>{revision?.content_hash?.slice(0, 16) ?? '—'}{revision ? '…' : ''}</code></dd></div></dl>{revision && <div className="site-success">Canonical revision {revision.revision} is persisted and downstream artifacts can bind to its revision hash.</div>}</aside>
    </div>
    {revision && <><SiteProviderPanel api={api} token={token} siteId={revision.site_id} revision={revision.site_revision_id} onFetched={() => setLayerRefresh(value => value + 1)} /><DiagramStudio api={api} token={token} siteId={revision.site_id} revision={revision.site_revision_id} /><EvidencePanel api={api} token={token} siteId={revision.site_id} /><RevisionHistory api={api} token={token} siteId={revision.site_id} currentRevision={revision.site_revision_id} /></>}
  </section>;
}

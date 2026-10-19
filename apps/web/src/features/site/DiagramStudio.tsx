import { useState } from 'react';

type DiagramType = 'figure_ground' | 'movement' | 'land_use' | 'green_water' | 'solar';
const DIAGRAMS: Array<[DiagramType, string]> = [['figure_ground', 'Figure-ground'], ['movement', 'Movement / access'], ['land_use', 'Land use'], ['green_water', 'Green / water'], ['solar', 'Solar / orientation']];

export default function DiagramStudio({ api, token, siteId, revision }: { api: string; token: string; siteId: string; revision: string }) {
  const [type, setType] = useState<DiagramType>('figure_ground');
  const [svg, setSvg] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  async function generate() {
    setBusy(true); setStatus('Generating deterministic diagram…');
    try {
      const response = await fetch(`${api}/sites/${siteId}/revisions/${revision}/diagrams/${type}`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Diagram generation failed');
      setSvg(data.svg); setStatus(`${data.status} · ${data.runner_version}`);
    } catch (error) { setSvg(''); setStatus(error instanceof Error ? error.message : 'Diagram generation failed'); }
    finally { setBusy(false); }
  }
  return <section className="phase-card" aria-label="Diagram studio">
    <div className="section-head"><div><p className="eyebrow">SITE / DIAGRAM STUDIO</p><h2>Evidence-backed diagrams</h2><p className="muted">Deterministic SVG projections of the canonical site revision and persisted analysis.</p></div><button className="btn primary" disabled={busy} onClick={generate}>{busy ? 'Generating…' : 'Generate diagram'}</button></div>
    <div className="diagram-tabs" role="tablist">{DIAGRAMS.map(([value, label]) => <button key={value} className={type === value ? 'active' : ''} role="tab" aria-selected={type === value} onClick={() => setType(value)}>{label}</button>)}</div>
    <div className="diagram-preview">{svg ? <iframe title={`${type} diagram`} sandbox="" srcDoc={svg} /> : <div className="empty-state"><h3>Choose a diagram</h3><p>Generate a diagram only after site analysis has been persisted.</p></div>}</div>
    {status && <div className="site-help" role="status">{status}</div>}
  </section>;
}

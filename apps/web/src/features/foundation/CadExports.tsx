import { useCallback, useEffect, useState } from 'react';

type ValidationCheck = { code: string; status: string; detail: string };
type ExportArtifact = {
  id: string;
  kind: string;
  filename: string;
  content_type: string;
  byte_size: number;
  sha256: string;
  media_role: string;
  download_path: string;
  validation: { status: string; checks: ValidationCheck[]; limitations?: string[] };
  artifact_status: string;
  exportable: boolean;
};
type ExportManifest = {
  status: string;
  project_id: string;
  project_version_id: string;
  world_model_hash: string;
  cad_job_run: { id: string; status: string; input_world_model_hash: string; stale: boolean } | null;
  artifacts: ExportArtifact[];
  message?: string;
};

export default function CadExports({ api, token, projectId, versionId }: {
  api: string; token: string; projectId: string; versionId: string;
}) {
  const [manifest, setManifest] = useState<ExportManifest | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    setError('');
    try {
      const response = await fetch(`${api}/projects/${projectId}/versions/${versionId}/cad/exports`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error?.message || data.detail || `Request failed (${response.status})`);
      setManifest(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load CAD/BIM exports');
    } finally {
      setBusy(false);
    }
  }, [api, token, projectId, versionId]);

  useEffect(() => { void load(); }, [load]);

  async function download(artifact: ExportArtifact) {
    setError('');
    try {
      const path = artifact.download_path.replace(/^\/api\/v1/, '');
      const response = await fetch(api + path, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error(`Download failed (${response.status})`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = artifact.filename;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed');
    }
  }

  return <div className="phase-card">
    <div className="card-actions">
      <div><p className="eyebrow">CAD / BIM INTEROPERABILITY</p><h2>Validated exports</h2></div>
      <button className="btn outline" disabled={busy} onClick={() => void load()}>{busy ? 'Checking…' : 'Refresh manifest'}</button>
    </div>
    <p className="muted">Checks verify file integrity and exchange-format structure. They do not certify design compliance or guarantee round-trip behaviour in every target application.</p>
    {error && <div className="alert">{error}</div>}
    {manifest && <>
      <div className={`quality-report ${manifest.status.toLowerCase()}`}>
        <strong>Manifest status: {manifest.status.replaceAll('_', ' ')}</strong>
        <p>{manifest.message || 'Manifest is bound to the selected version and canonical World Model hash.'}</p>
        <small>World Model hash: <code>{manifest.world_model_hash || '—'}</code></small>
        {manifest.cad_job_run && <small>CAD run: <code>{manifest.cad_job_run.id}</code> · {manifest.cad_job_run.status} · {manifest.cad_job_run.stale ? 'STALE' : 'hash-bound'}</small>}
      </div>
      {manifest.artifacts.length ? <div className="phase-grid">{manifest.artifacts.map(artifact =>
        <article className="fact-card" key={artifact.id}>
          <p className="eyebrow">{artifact.kind.replaceAll('_', ' ')} · {artifact.media_role}</p>
          <h3>{artifact.filename}</h3>
          <div className={`requirement-state ${artifact.artifact_status.toLowerCase()}`}>{artifact.exportable ? 'PASS · CURRENT' : artifact.artifact_status.replaceAll('_', ' ')}</div>
          <p>{(artifact.byte_size / 1024).toFixed(1)} KiB · SHA-256 <code>{artifact.sha256.slice(0, 16)}…</code></p>
          <ul>{artifact.validation.checks.filter(check => check.status !== 'PASS').map((check, index) =>
            <li key={`${check.code}-${index}`}><b>{check.code}</b> — {check.detail}</li>)}</ul>
          <button className="btn primary small" disabled={!artifact.exportable} onClick={() => void download(artifact)}>Download validated export</button>
        </article>
      )}</div> : <div className="empty-state"><h3>No CAD/BIM artifacts</h3><p>{manifest.message || 'Generate CAD from a current design alternative to create exchange files.'}</p></div>}
    </>}
  </div>;
}

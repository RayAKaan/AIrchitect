import { useEffect, useMemo, useReducer, useState } from 'react';
import DesignWorkspace from '../design/DesignWorkspace';
import ChangeImpactPanel from './ChangeImpactPanel';
import ReleaseValidation from './ReleaseValidation';
import SemanticEditor from './SemanticEditor';
import S2BriefWorkspace from './S2BriefWorkspace';
import S2ConceptGenerationWorkspace from './S2ConceptGenerationWorkspace';
import S2ConceptExplorer from './S2ConceptExplorer';
import S2RequirementsWorkspace from './S2RequirementsWorkspace';
import SiteWorkspace from '../site/SiteWorkspace';
import CadExports from './CadExports';
import WorkspaceFlow from './WorkspaceFlow';
import {
  ADVANCED_STAGES,
  createWorkspaceState,
  persistWorkspace,
  PRODUCT_MODES,
  readPersistedWorkspace,
  workspaceReducer,
  type AdvancedStage,
  type ProductMode,
  type WorkspaceState,
} from '../../state/productWorkspace';
import './UnifiedWorkspace.css';

type Version = { id: string; version_number: number; label: string; status: string; revision_number: number; created_at: string };
type Snapshot = { project: any; version: Version; brief: any; requirements: any[]; assumptions: any[]; world_model: any; world_model_revision: any };

const MODE_COPY: Record<ProductMode, { title: string; description: string }> = {
  Brief: { title: 'Tell AIrchitect what you are building.', description: 'Start with intent. AIrchitect will keep the source brief separate from extracted facts and decisions.' },
  Site: { title: 'Understand the place.', description: 'Review the site boundary and site intelligence before shaping the building.' },
  Explore: { title: 'Explore possibilities.', description: 'Generate and compare deterministic concepts from the current canonical project state.' },
  Design: { title: 'Develop the chosen direction.', description: 'Work with alternatives, geometry, quantities, engineering screening and evidence.' },
  Validate: { title: 'Check the decisions.', description: 'Review release validation and the downstream impact of the current version.' },
  Deliver: { title: 'Prepare the professional outputs.', description: 'Generate and review the CAD/BIM exchange artifacts for the selected canonical version.' },
};

const STAGE_TO_LABEL: Record<AdvancedStage, string> = {
  Brief: 'Brief',
  'World Model': 'World model',
  'Semantic Model': 'Semantic model',
  Design: 'Design',
  'CAD/BIM Exports': 'CAD/BIM',
  Engineering: 'Engineering',
  'Change Impact': 'Change impact',
  'Release Validation': 'Release validation',
  Regulatory: 'Regulatory',
};

export default function UnifiedWorkspace({ api, token, project, onClose }: { api: string; token: string; project: any; onClose: () => void }) {
  const [state, dispatch] = useReducer(
    workspaceReducer,
    project.id,
    (projectId) => createWorkspaceState(projectId, readPersistedWorkspace(projectId)),
  );
  const [versions, setVersions] = useState<Version[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  useEffect(() => {
    persistWorkspace(state);
    window.history.replaceState({}, '', `?project=${encodeURIComponent(project.id)}&mode=${encodeURIComponent(state.mode)}`);
    window.dispatchEvent(new CustomEvent('airchitect:workspace-state', { detail: state }));
  }, [project.id, state]);

  async function request(path: string, init: RequestInit = {}) {
    const response = await fetch(api + path, { ...init, headers: { ...headers, ...init.headers } });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error?.message || data.detail?.error?.message || data.detail || `Request failed (${response.status})`);
    return data;
  }

  async function loadVersions(prefer?: string | null) {
    const data = await request(`/projects/${project.id}/versions`);
    const nextVersions = data.versions || [];
    setVersions(nextVersions);
    const nextId = prefer || state.versionId || data.current_version_id || nextVersions[0]?.id || null;
    if (nextId !== state.versionId) dispatch({ type: 'select-version', versionId: nextId });
  }

  async function loadSnapshot(versionId = state.versionId) {
    if (!versionId) return;
    setBusy(true);
    try {
      setSnapshot(await request(`/projects/${project.id}/versions/${versionId}/snapshot`));
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load canonical project state.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void loadVersions();
  }, [project.id]);

  useEffect(() => {
    void loadSnapshot();
  }, [state.versionId]);

  function selectMode(mode: ProductMode) {
    dispatch({ type: 'select-mode', mode });
  }

  function selectStage(stage: string) {
    if (ADVANCED_STAGES.includes(stage as AdvancedStage)) dispatch({ type: 'select-stage', stage: stage as AdvancedStage });
  }

  async function refresh() {
    await loadVersions(state.versionId);
    await loadSnapshot(state.versionId);
  }

  const currentVersion = snapshot?.version || versions.find((version) => version.id === state.versionId) || null;
  const advanced = state.advancedOpen;

  return (
    <section className="unified-workspace" aria-label="AIrchitect project workspace">
      <header className="unified-header">
        <div className="unified-title">
          <button className="product-back" onClick={onClose} aria-label="Back to projects">← Projects</button>
          <div><p className="eyebrow">AIrchitect / project workspace</p><h1>{project.name}</h1></div>
        </div>
        <div className="unified-header-actions">
          <label className="version-picker">Version
            <select value={state.versionId || ''} onChange={(event) => dispatch({ type: 'select-version', versionId: event.target.value || null })} aria-label="Project version">
              {versions.map((version) => <option key={version.id} value={version.id}>{version.label} · {version.status}</option>)}
            </select>
          </label>
          <button className="btn outline" onClick={refresh} disabled={busy}>Refresh</button>
          <button className="btn outline" aria-pressed={advanced} onClick={() => dispatch({ type: 'toggle-advanced' })}>{advanced ? 'Simple view' : 'Advanced'}</button>
        </div>
      </header>

      <nav className="unified-mode-bar" aria-label="Project workflow">
        {PRODUCT_MODES.map((mode, index) => (
          <button key={mode} className={`unified-mode ${state.mode === mode ? 'active' : ''}`} onClick={() => selectMode(mode)} aria-current={state.mode === mode ? 'step' : undefined}>
            <span className="unified-mode-number">{index + 1}</span>
            <span><b>{mode}</b><small>{MODE_COPY[mode].description}</small></span>
          </button>
        ))}
      </nav>

      {advanced && <div className="unified-advanced">
        <div className="unified-advanced-heading"><div><span className="eyebrow">PROFESSIONAL WORKFLOW</span><strong>Canonical delivery stages</strong></div><small>Advanced tools stay available without changing the default experience.</small></div>
        <WorkspaceFlow active={state.advancedStage} onSelect={selectStage} />
      </div>}

      <div className="unified-context">
        <div><span className="eyebrow">{state.mode.toUpperCase()}</span><h2>{MODE_COPY[state.mode].title}</h2><p>{MODE_COPY[state.mode].description}</p></div>
        <div className="canonical-context" aria-label="Canonical version context"><span>{currentVersion?.label || 'No version'}</span><span>{currentVersion?.status || 'Loading'}</span><span>Revision {currentVersion?.revision_number ?? '—'}</span></div>
      </div>

      {error && <div className="alert" role="alert">{error}</div>}
      {busy && <div className="progress-line" aria-label="Loading canonical project state" />}

      <main className="unified-content">
        {advanced ? renderAdvancedStage(state.advancedStage) : renderMode(state.mode)}
      </main>
    </section>
  );

  function requireSnapshot() {
    if (!snapshot || !currentVersion) return <div className="unified-empty"><h3>Canonical state is loading</h3><p>AIrchitect is loading the selected project version. Nothing is changed while this is happening.</p></div>;
    return null;
  }

  function renderMode(mode: ProductMode) {
    const loading = requireSnapshot();
    if (loading) return loading;
    if (mode === 'Site') return <SiteWorkspace api={api} token={token} project={project} />;
    if (mode === 'Design') return <DesignWorkspace api={api} token={token} projectId={project.id} organizationId={snapshot!.project.organization_id} version={currentVersion!} />;
    if (mode === 'Validate') return <ReleaseValidation api={api} token={token} projectId={project.id} version={currentVersion!} snapshot={snapshot!} />;
    if (mode === 'Deliver') return <CadExports api={api} token={token} projectId={project.id} versionId={currentVersion!.id} />;
    if (mode === 'Explore') return <div className="unified-stack"><S2ConceptGenerationWorkspace api={api} token={token} projectId={project.id} version={currentVersion!} /><S2ConceptExplorer api={api} token={token} projectId={project.id} version={currentVersion!} /></div>;
    return <S2BriefWorkspace api={api} token={token} projectId={project.id} version={currentVersion!} brief={snapshot!.brief} onRefresh={refresh} />;
  }

  function renderAdvancedStage(stage: AdvancedStage) {
    const loading = requireSnapshot();
    if (loading) return loading;
    switch (stage) {
      case 'Brief': return <S2BriefWorkspace api={api} token={token} projectId={project.id} version={currentVersion!} brief={snapshot!.brief} onRefresh={refresh} />;
      case 'World Model': return <WorldModelReview snapshot={snapshot!} />;
      case 'Semantic Model': return <SemanticEditor api={api} token={token} projectId={project.id} version={currentVersion!} onChanged={refresh} />;
      case 'Design': return <DesignWorkspace api={api} token={token} projectId={project.id} organizationId={snapshot!.project.organization_id} version={currentVersion!} />;
      case 'CAD/BIM Exports': return <CadExports api={api} token={token} projectId={project.id} versionId={currentVersion!.id} />;
      case 'Engineering': return <DesignWorkspace api={api} token={token} projectId={project.id} organizationId={snapshot!.project.organization_id} version={currentVersion!} />;
      case 'Change Impact': return <ChangeImpactPanel api={api} token={token} projectId={project.id} version={currentVersion!} />;
      case 'Release Validation': return <ReleaseValidation api={api} token={token} projectId={project.id} version={currentVersion!} snapshot={snapshot!} />;
      case 'Regulatory': return <ReleaseValidation api={api} token={token} projectId={project.id} version={currentVersion!} snapshot={snapshot!} />;
    }
  }
}

function WorldModelReview({ snapshot }: { snapshot: Snapshot }) {
  const sections = [
    ['Site', snapshot.world_model?.site],
    ['Building', snapshot.world_model?.building],
    ['Parking', snapshot.world_model?.parking],
    ['Structural grid', snapshot.world_model?.structural_grid],
    ['Levels', snapshot.world_model?.levels],
  ];
  return <section className="unified-world-model"><div className="phase-card"><p className="eyebrow">CANONICAL WORLD MODEL</p><h2>{snapshot.version.label}</h2><div className="unified-world-grid">{sections.map(([title, value]) => <article key={title as string}><h3>{title}</h3><pre>{JSON.stringify(value ?? null, null, 2)}</pre></article>)}</div></div><aside className="phase-card"><p className="eyebrow">PROVENANCE</p>{Object.entries(snapshot.world_model?.provenance || {}).map(([key, value]: any) => <div className="unified-provenance" key={key}><b>{key}</b><span>{value.source_type} · {value.confirmed ? 'confirmed' : 'unconfirmed'}</span></div>)}<p className="eyebrow">UNKNOWN VALUES</p>{(snapshot.world_model?.unknowns || []).map((item: string) => <div className="unified-unknown" key={item}>? {item}</div>)}</aside></section>;
}

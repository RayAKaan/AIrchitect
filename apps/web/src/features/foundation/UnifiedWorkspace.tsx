import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import DesignWorkspace from '../design/DesignWorkspace';
import ChangeImpactPanel from './ChangeImpactPanel';
import ReleaseValidation from './ReleaseValidation';
import SemanticEditor from './SemanticEditor';
import S2BriefWorkspace from './S2BriefWorkspace';
import S2ProgramWorkspace from './S2ProgramWorkspace';
import S2EnvelopeWorkspace from './S2EnvelopeWorkspace';
import ExploreWorkspace from './ExploreWorkspace';
import SiteWorkspace from '../site/SiteWorkspace';
import CadExports from './CadExports';
import WorkspaceFlow from './WorkspaceFlow';
import ProgressiveDisclosure from '../home/ProgressiveDisclosure';
import NextActionCard from '../home/NextActionCard';
import UnifiedAgentBar from '../home/UnifiedAgentBar';
import AIExplanationPanel from '../home/AIExplanationPanel';
import RequirementsLifecyclePanel from '../home/RequirementsLifecyclePanel';
import ConstraintWorkspacePanel from './ConstraintWorkspacePanel';
import { ADVANCED_STAGES, createWorkspaceState, persistWorkspace, PRODUCT_MODES, readPersistedWorkspace, workspaceReducer, type AdvancedStage, type ProductMode } from '../../state/productWorkspace';
import { buildWorkspaceUrl, parseWorkspaceUrl } from '../../state/workspaceNavigation';
import { assertUnreachable, resolveModeView } from '../../state/workspaceModeRouting';
import { assertUnreachableAdvancedView, resolveAdvancedStageView } from '../../state/workspaceAdvancedRouting';
import { resolveVersionContext } from '../../state/workspaceVersionContext';
import { savePendingOnboarding, takePendingOnboarding } from '../home/projectOnboarding';
import './UnifiedWorkspace.css';

type Version = { id: string; version_number: number; label: string; status: string; revision_number: number; created_at: string };
type Snapshot = { project: any; version: Version; brief: any; requirements: any[]; assumptions: any[]; world_model: any; world_model_revision: any };
const MODE_COPY: Record<ProductMode, { title: string; description: string }> = { Brief: { title: 'Tell AIrchitect what you are building.', description: 'Start with intent. AIrchitect will keep the source brief separate from extracted facts and decisions.' }, Site: { title: 'Understand the place.', description: 'Review the site boundary and site intelligence before shaping the building.' }, Explore: { title: 'Explore possibilities.', description: 'Generate and compare deterministic concept alternatives from the current program, constraints and buildable envelope.' }, Design: { title: 'Develop the chosen direction.', description: 'Work with alternatives, geometry, quantities, engineering screening and evidence.' }, Validate: { title: 'Check the decisions.', description: 'Review release validation and the downstream impact of the current version.' }, Deliver: { title: 'Prepare the professional outputs.', description: 'Generate and review the CAD/BIM exchange artifacts for the selected canonical version.' } };

export default function UnifiedWorkspace({ api, token, project, onClose }: { api: string; token: string; project: any; onClose: () => void }) {
  const [state, dispatch] = useReducer(workspaceReducer, project.id, (projectId) => { const query = parseWorkspaceUrl(window.location.search); const persisted = readPersistedWorkspace(projectId) || {}; return createWorkspaceState(projectId, { ...persisted, mode: query.mode || persisted.mode, versionId: query.versionId || persisted.versionId }); });
  const [versions, setVersions] = useState<Version[]>([]); const [snapshot, setSnapshot] = useState<Snapshot | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);
  const routeStateRef = useRef({ projectId: state.projectId, mode: state.mode, versionId: state.versionId });
  useEffect(() => {
    persistWorkspace(state);
    const previous = routeStateRef.current;
    const routeChanged = previous.projectId !== state.projectId || previous.mode !== state.mode;
    const nextUrl = buildWorkspaceUrl(window.location.pathname, state, window.location.search, window.location.hash);
    const currentUrl = window.location.pathname + window.location.search + window.location.hash;
    if (nextUrl !== currentUrl) {
      if (routeChanged) window.history.pushState({}, '', nextUrl);
      else window.history.replaceState({}, '', nextUrl);
    }
    routeStateRef.current = { projectId: state.projectId, mode: state.mode, versionId: state.versionId };
    window.dispatchEvent(new CustomEvent('airchitect:workspace-state', { detail: state }));
  }, [project.id, state]);
  useEffect(() => {
    function onPopState() {
      const next = parseWorkspaceUrl(window.location.search);
      const nextMode = next.mode ?? state.mode;
      routeStateRef.current = { projectId: state.projectId, mode: nextMode, versionId: next.versionId };
      if (!next.mode) {
        const canonicalUrl = buildWorkspaceUrl(window.location.pathname, { ...state, mode: nextMode, versionId: next.versionId }, window.location.search, window.location.hash);
        window.history.replaceState({}, '', canonicalUrl);
      }
      if (next.mode && next.mode !== state.mode) dispatch({ type: 'select-mode', mode: next.mode });
      if (next.versionId !== state.versionId) dispatch({ type: 'select-version', versionId: next.versionId });
      if (!next.versionId) void loadVersions(null);
    }
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [state.projectId, state.mode, state.versionId]);
  async function request(path: string, init: RequestInit = {}, signal?: AbortSignal) { const response = await fetch(api + path, { ...init, signal, headers: { ...headers, ...init.headers } }); const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.error?.message || data.detail?.error?.message || data.detail || `Request failed (${response.status})`); return data; }
  async function loadVersions(prefer?: string | null, signal?: AbortSignal): Promise<string | null> {
    try {
      const data = await request('/projects/' + project.id + '/versions', {}, signal);
      if (signal?.aborted) return null;
      const nextVersions: Version[] = Array.isArray(data.versions)
        ? data.versions.filter((value: unknown): value is Version =>
            Boolean(value)
            && typeof value === 'object'
            && typeof (value as Version).id === 'string'
            && typeof (value as Version).label === 'string'
            && typeof (value as Version).status === 'string'
            && typeof (value as Version).version_number === 'number'
            && typeof (value as Version).revision_number === 'number'
            && typeof (value as Version).created_at === 'string')
        : [];
      setVersions(nextVersions);
      const requestedId = prefer === undefined ? state.versionId : prefer;
      const serverCurrentId = typeof data.current_version_id === 'string' ? data.current_version_id : null;
      const nextId = requestedId && nextVersions.some((version) => version.id === requestedId)
        ? requestedId
        : serverCurrentId && nextVersions.some((version) => version.id === serverCurrentId)
          ? serverCurrentId
          : nextVersions[0]?.id ?? null;
      if (nextId !== state.versionId) dispatch({ type: 'select-version', versionId: nextId });
      return nextId;
    } catch (cause) {
      if (!signal?.aborted && (cause as Error).name !== 'AbortError') {
        setError(cause instanceof Error ? cause.message : 'Could not load project versions.');
      }
      return null;
    }
  }
  async function loadSnapshot(versionId: string | null, signal?: AbortSignal) {
    if (!versionId) {
      setSnapshot(null);
      setBusy(false);
      return;
    }
    setSnapshot((current) => current?.version?.id === versionId ? current : null);
    setBusy(true);
    try {
      const data = await request('/projects/' + project.id + '/versions/' + versionId + '/snapshot', {}, signal);
      if (signal?.aborted) return;
      if (data?.version?.id !== versionId) {
        throw new Error('The server returned a snapshot for a different project version.');
      }
      setSnapshot(data);
      setError('');
    } catch (cause) {
      if (!signal?.aborted && (cause as Error).name !== 'AbortError') {
        setError(cause instanceof Error ? cause.message : 'Could not load canonical project state.');
      }
    } finally {
      if (!signal?.aborted) setBusy(false);
    }
  }
  useEffect(() => { const controller = new AbortController(); void loadVersions(undefined, controller.signal); return () => controller.abort(); }, [project.id]);
  useEffect(() => { const controller = new AbortController(); void loadSnapshot(state.versionId, controller.signal); return () => controller.abort(); }, [project.id, state.versionId]);
  useEffect(() => { if (!state.versionId || !versions.length) return; const version = versions.find((item) => item.id === state.versionId); if (!version || version.status !== 'DRAFT') return; const pending = takePendingOnboarding(project.id); if (!pending) return; void request(`/projects/${project.id}/versions/${state.versionId}/brief`, { method: 'PUT', body: JSON.stringify({ text: pending, source_reference: 'AIrchitect natural-language onboarding', source_type: 'USER_BRIEF' }) }).then(() => loadSnapshot(state.versionId)).catch((cause) => { savePendingOnboarding(project.id, pending); setError(cause instanceof Error ? cause.message : 'Could not persist the onboarding brief.'); }); }, [project.id, state.versionId, versions]);
  function selectStage(stage: string) { if (ADVANCED_STAGES.includes(stage as AdvancedStage)) dispatch({ type: 'select-stage', stage: stage as AdvancedStage }); }
  async function refresh() {
    const versionId = await loadVersions(state.versionId);
    if (versionId === state.versionId) await loadSnapshot(versionId);
  }
  const { currentVersion, currentSnapshot } = resolveVersionContext(state.versionId, versions, snapshot);
  const advanced = state.advancedOpen;
  const agentContext = currentSnapshot
    ? JSON.stringify({ brief: currentSnapshot.brief, requirements: currentSnapshot.requirements, assumptions: currentSnapshot.assumptions, world_model: currentSnapshot.world_model }, null, 2)
    : 'Canonical project state is still loading.';
  const programWorkspace = currentVersion ? <S2ProgramWorkspace api={api} token={token} projectId={project.id} version={currentVersion} /> : null;
  const envelopeWorkspace = currentVersion ? <S2EnvelopeWorkspace api={api} token={token} projectId={project.id} version={currentVersion} /> : null;

  return <section className="unified-workspace" aria-label="AIrchitect project workspace"><header className="unified-header"><div className="unified-title"><button className="product-back" onClick={onClose} aria-label="Back to projects">← Projects</button><div><p className="eyebrow">AIrchitect / project workspace</p><h1>{project.name}</h1></div></div><div className="unified-header-actions"><label className="version-picker">Version<select value={state.versionId || ''} onChange={(event) => dispatch({ type: 'select-version', versionId: event.target.value || null })} aria-label="Project version">{versions.map((version) => <option key={version.id} value={version.id}>{version.label} · {version.status}</option>)}</select></label><button className="btn outline" onClick={refresh} disabled={busy}>Refresh</button><button className="btn outline" aria-pressed={advanced} onClick={() => dispatch({ type: 'toggle-advanced' })}>{advanced ? 'Simple view' : 'Advanced'}</button></div></header><nav className="unified-mode-bar" aria-label="Project workflow">{PRODUCT_MODES.map((mode, index) => <button key={mode} className={`unified-mode ${state.mode === mode ? 'active' : ''}`} onClick={() => dispatch({ type: 'select-mode', mode })} aria-current={state.mode === mode ? 'step' : undefined}><span className="unified-mode-number">{index + 1}</span><span><b>{mode}</b><small>{MODE_COPY[mode].description}</small></span></button>)}</nav>{advanced && <div className="unified-advanced"><div className="unified-advanced-heading"><div><span className="eyebrow">PROFESSIONAL WORKFLOW</span><strong>Canonical delivery stages</strong></div><small>Advanced tools stay available without changing the default experience.</small></div><WorkspaceFlow active={state.advancedStage} onSelect={selectStage} /></div>}<div className="unified-context"><div><span className="eyebrow">{state.mode.toUpperCase()}</span><h2>{MODE_COPY[state.mode].title}</h2><p>{MODE_COPY[state.mode].description}</p></div><div className="canonical-context" aria-label="Canonical version context"><span>{currentVersion?.label || 'No version'}</span><span>{currentVersion?.status || 'Loading'}</span><span>Revision {currentVersion?.revision_number ?? '—'}</span></div></div>{currentVersion && <UnifiedAgentBar projectId={project.id} versionId={currentVersion.id} mode={state.mode} context={agentContext}/>} {!advanced && <><NextActionCard mode={state.mode} snapshot={currentSnapshot} status={currentVersion?.status || 'LOADING'} onNavigate={(mode) => dispatch({ type: 'select-mode', mode })}/><AIExplanationPanel mode={state.mode} snapshot={currentSnapshot}/><ProgressiveDisclosure mode={state.mode} onOpenAdvanced={() => dispatch({ type: 'toggle-advanced', open: true })}/></>}{error && <div className="alert" role="alert">{error}</div>}{busy && <div className="progress-line" aria-label="Loading canonical project state" />}<main className="unified-content">{advanced ? renderAdvancedStage(state.advancedStage) : renderMode(state.mode)}</main></section>;
  function requireSnapshot() { return !currentSnapshot || !currentVersion ? <div className="unified-empty"><h3>Canonical state is loading</h3><p>AIrchitect is loading the selected project version. Nothing is changed while this is happening.</p></div> : null; }
  function renderMode(mode: ProductMode) {
    const loading = requireSnapshot();
    if (loading) return loading;

    const target = resolveModeView(mode);
    switch (target) {
      case 'site':
        return <SiteWorkspace api={api} token={token} project={project} />;
      case 'design':
        return <DesignWorkspace api={api} token={token} projectId={project.id} organizationId={snapshot!.project.organization_id} version={currentVersion!} />;
      case 'validate':
        return <ReleaseValidation api={api} token={token} projectId={project.id} version={currentVersion!} snapshot={snapshot!} />;
      case 'deliver':
        return <CadExports api={api} token={token} projectId={project.id} versionId={currentVersion!.id} />;
      case 'explore':
        return <ExploreWorkspace api={api} token={token} projectId={project.id} version={currentVersion!} onOpenWorldModel={() => dispatch({ type: 'select-stage', stage: 'World Model' })} />;
      case 'brief':
        return <div className="unified-stack"><S2BriefWorkspace api={api} token={token} projectId={project.id} version={currentVersion!} brief={snapshot!.brief} onRefresh={refresh}/><RequirementsLifecyclePanel api={api} token={token} projectId={project.id} versionId={currentVersion!.id} revision={currentVersion!.revision_number} onChanged={refresh}/><ConstraintWorkspacePanel projectId={project.id} versionId={currentVersion!.id} requirements={snapshot!.requirements}/>{programWorkspace}{envelopeWorkspace}</div>;
      default:
        return assertUnreachable(target);
    }
  }
  function renderAdvancedStage(stage: AdvancedStage) {
    const loading = requireSnapshot();
    if (loading) return loading;

    const target = resolveAdvancedStageView(stage);
    switch (target) {
      case 'brief':
        return <div className="unified-stack"><S2BriefWorkspace api={api} token={token} projectId={project.id} version={currentVersion!} brief={snapshot!.brief} onRefresh={refresh}/><RequirementsLifecyclePanel api={api} token={token} projectId={project.id} versionId={currentVersion!.id} revision={currentVersion!.revision_number} onChanged={refresh}/><ConstraintWorkspacePanel projectId={project.id} versionId={currentVersion!.id} requirements={snapshot!.requirements}/>{programWorkspace}{envelopeWorkspace}</div>;
      case 'world-model':
        return <WorldModelReview snapshot={snapshot!} />;
      case 'semantic-model':
        return <SemanticEditor api={api} token={token} projectId={project.id} version={currentVersion!} onChanged={refresh} />;
      case 'design':
      case 'engineering':
        return <DesignWorkspace api={api} token={token} projectId={project.id} organizationId={snapshot!.project.organization_id} version={currentVersion!} />;
      case 'deliver':
        return <CadExports api={api} token={token} projectId={project.id} versionId={currentVersion!.id} />;
      case 'change-impact':
        return <ChangeImpactPanel api={api} token={token} projectId={project.id} version={currentVersion!} />;
      case 'release-validation':
      case 'regulatory':
        return <ReleaseValidation api={api} token={token} projectId={project.id} version={currentVersion!} snapshot={snapshot!} />;
      default:
        return assertUnreachableAdvancedView(target);
    }
  }
}
function WorldModelReview({ snapshot }: { snapshot: Snapshot }) { const sections = [['Site', snapshot.world_model?.site], ['Building', snapshot.world_model?.building], ['Parking', snapshot.world_model?.parking], ['Structural grid', snapshot.world_model?.structural_grid], ['Levels', snapshot.world_model?.levels]]; return <section className="unified-world-model"><div className="phase-card"><p className="eyebrow">CANONICAL WORLD MODEL</p><h2>{snapshot.version.label}</h2><div className="unified-world-grid">{sections.map(([title, value]) => <article key={title as string}><h3>{title}</h3><pre>{JSON.stringify(value ?? null, null, 2)}</pre></article>)}</div></div><aside className="phase-card"><p className="eyebrow">PROVENANCE</p>{Object.entries(snapshot.world_model?.provenance || {}).map(([key, value]: any) => <div className="unified-provenance" key={key}><b>{key}</b><span>{value.source_type} · {value.confirmed ? 'confirmed' : 'unconfirmed'}</span></div>)}<p className="eyebrow">UNKNOWN VALUES</p>{(snapshot.world_model?.unknowns || []).map((item: string) => <div className="unified-unknown" key={item}>? {item}</div>)}</aside></section>; }

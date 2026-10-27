import { useState } from 'react';
import FoundationWorkspace from './FoundationWorkspace';
import WorkspaceFlow from './WorkspaceFlow';
import './ProductWorkspace.css';

type Mode = 'Brief' | 'Site' | 'Explore' | 'Design' | 'Validate' | 'Deliver';
const MODES: Array<{id:Mode; label:string; hint:string}> = [
  { id: 'Brief', label: 'Brief', hint: 'Define the project' }, { id: 'Site', label: 'Site', hint: 'Understand the place' },
  { id: 'Explore', label: 'Explore', hint: 'Generate possibilities' }, { id: 'Design', label: 'Design', hint: 'Develop the chosen scheme' },
  { id: 'Validate', label: 'Validate', hint: 'Check decisions and impacts' }, { id: 'Deliver', label: 'Deliver', hint: 'Prepare professional outputs' },
];
const MODE_TABS: Record<Mode, string> = { Brief: 'Brief', Site: 'Site', Explore: 'S2', Design: 'Design', Validate: 'Release Validation', Deliver: 'CAD/BIM Exports' };
const ADVANCED_STAGES = ['Brief', 'World Model', 'Semantic Model', 'Design', 'CAD/BIM Exports', 'Engineering', 'Change Impact', 'Release Validation', 'Regulatory'];

export default function ProductWorkspace({ api, token, project, onClose }: { api: string; token: string; project: any; onClose: () => void }) {
  const [active, setActive] = useState<Mode>(() => { const raw = sessionStorage.getItem(`airchitect:mode:${project.id}`) as Mode | null; return raw && MODES.some((mode) => mode.id === raw) ? raw : 'Brief'; });
  function selectMode(mode: Mode) { setActive(mode); sessionStorage.setItem(`airchitect:mode:${project.id}`, mode); window.dispatchEvent(new CustomEvent('airchitect:product-mode', { detail: { mode, tab: MODE_TABS[mode], projectId: project.id } })); }
  function selectStage(stage: string) { window.dispatchEvent(new CustomEvent('airchitect:workspace-stage', { detail: { stage, projectId: project.id } })); }
  return <section className="product-workspace" aria-label="AIrchitect project workspace">
    <header className="product-workspace-header"><div className="product-workspace-title"><button className="product-back" onClick={onClose} aria-label="Back to projects">← Projects</button><div><p className="eyebrow">AIrchitect workspace</p><h1>{project.name}</h1></div></div><div className="product-status" aria-label="Project status"><span className="status-dot" /> Canonical project state</div></header>
    <nav className="product-mode-bar" aria-label="Project workflow">{MODES.map((mode, index) => <button key={mode.id} className={`product-mode ${mode.id === active ? 'active' : ''}`} onClick={() => selectMode(mode.id)} title={mode.hint} aria-label={`${mode.label} mode`}><span className="product-mode-number">{index + 1}</span><span><b>{mode.label}</b><small>{mode.hint}</small></span></button>)}</nav>
    <div className="product-advanced-flow"><span className="product-advanced-label">Advanced workflow</span><WorkspaceFlow active="Brief" onSelect={selectStage} /><div className="product-advanced-compat" aria-label="Advanced workflow stages">{ADVANCED_STAGES.map((stage) => <button key={stage} className="product-advanced-compat-button" onClick={() => selectStage(stage)}>{stage}</button>)}</div></div>
    <FoundationWorkspace api={api} token={token} project={project} onClose={onClose} />
  </section>;
}

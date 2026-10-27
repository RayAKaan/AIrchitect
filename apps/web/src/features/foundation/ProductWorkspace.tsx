import { useMemo } from 'react';
import FoundationWorkspace from './FoundationWorkspace';
import './ProductWorkspace.css';

type Mode = 'Brief' | 'Site' | 'Explore' | 'Design' | 'Validate' | 'Deliver';

const MODES: Array<{id:Mode; label:string; hint:string}> = [
  { id: 'Brief', label: 'Brief', hint: 'Define the project' },
  { id: 'Site', label: 'Site', hint: 'Understand the place' },
  { id: 'Explore', label: 'Explore', hint: 'Generate possibilities' },
  { id: 'Design', label: 'Design', hint: 'Develop the chosen scheme' },
  { id: 'Validate', label: 'Validate', hint: 'Check decisions and impacts' },
  { id: 'Deliver', label: 'Deliver', hint: 'Prepare professional outputs' },
];

const MODE_TABS: Record<Mode, string> = {
  Brief: 'Brief',
  Site: 'Site',
  Explore: 'Design',
  Design: 'Semantic Model',
  Validate: 'Release Validation',
  Deliver: 'CAD/BIM Exports',
};

export default function ProductWorkspace({ api, token, project, onClose }: { api: string; token: string; project: any; onClose: () => void }) {
  const active = useMemo<Mode>(() => {
    const raw = sessionStorage.getItem(`airchitect:mode:${project.id}`) as Mode | null;
    return raw && MODES.some((mode) => mode.id === raw) ? raw : 'Brief';
  }, [project.id]);

  function selectMode(mode: Mode) {
    sessionStorage.setItem(`airchitect:mode:${project.id}`, mode);
    window.dispatchEvent(new CustomEvent('airchitect:product-mode', { detail: { mode, tab: MODE_TABS[mode], projectId: project.id } }));
  }

  return (
    <section className="product-workspace" aria-label="AIrchitect project workspace">
      <header className="product-workspace-header">
        <div className="product-workspace-title">
          <button className="product-back" onClick={onClose} aria-label="Back to projects">← Projects</button>
          <div>
            <p className="eyebrow">AIrchitect workspace</p>
            <h1>{project.name}</h1>
          </div>
        </div>
        <div className="product-status" aria-label="Project status">
          <span className="status-dot" /> Canonical project state
        </div>
      </header>

      <nav className="product-mode-bar" aria-label="Project workflow">
        {MODES.map((mode, index) => (
          <button
            key={mode.id}
            className={`product-mode ${mode.id === active ? 'active' : ''}`}
            onClick={() => selectMode(mode.id)}
            title={mode.hint}
          >
            <span className="product-mode-number">{index + 1}</span>
            <span><b>{mode.label}</b><small>{mode.hint}</small></span>
          </button>
        ))}
      </nav>

      <FoundationWorkspace api={api} token={token} project={project} onClose={onClose} />
    </section>
  );
}

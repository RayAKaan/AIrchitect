import { useMemo, useState } from 'react';
import './AIHomeWorkspace.css';

type Project = { id: string; name: string; building_type?: string; location?: string; status?: string; version?: string | number };

type Props = {
  projects: Project[];
  organizationName?: string;
  onOpenProject: (project: Project) => void;
  onCreateProject: (name: string) => Promise<void>;
  onSettings: () => void;
  onSignOut: () => void;
};

const EXAMPLES = ['A six-floor retail centre in Riyadh', 'A compact cafe with outdoor seating', 'A mixed-use building for a constrained urban site'];

export default function AIHomeWorkspace({ projects, organizationName, onOpenProject, onCreateProject, onSettings, onSignOut }: Props) {
  const [intent, setIntent] = useState('');
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState('');
  const recent = useMemo(() => projects.slice(0, 4), [projects]);

  async function createFromIntent() {
    const name = intent.trim().split(/[.!?\n]/)[0].slice(0, 72) || 'Untitled architectural project';
    setCreating(true); setError('');
    try { await onCreateProject(name); setIntent(''); setShowCreate(false); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not create the project.'); }
    finally { setCreating(false); }
  }

  return <section className="ai-home" aria-label="AIrchitect home">
    <header className="ai-home-nav"><div className="ai-home-brand"><span className="ai-home-mark">N</span><span>NAZMAK<small>BUILDING INTELLIGENCE</small></span></div><div className="ai-home-org"><span>{organizationName || 'Workspace'}</span><button className="home-nav-button" onClick={onSettings}>Settings</button><button className="home-nav-button" onClick={onSignOut}>Sign out</button></div></header>

    <main className="ai-home-main">
      <div className="ai-home-hero"><p className="eyebrow">AIrchitect</p><h1>What are you building?</h1><p>Describe the project in your own words. You can stay at this simple level, or open the professional tools when you need them.</p>
        <div className="ai-prompt-card"><textarea value={intent} onChange={(event) => setIntent(event.target.value)} placeholder="e.g. I need a six-floor commercial building in Riyadh with around 8,000 m² of GFA…" aria-label="Describe what you are building" rows={4}/><div className="ai-prompt-footer"><div className="prompt-hints">{EXAMPLES.map((example) => <button key={example} onClick={() => setIntent(example)}>{example}</button>)}</div><button className="btn primary" onClick={createFromIntent} disabled={creating || !intent.trim()}>{creating ? 'Starting…' : 'Start project'} ↗</button></div></div>
        {error && <div className="alert" role="alert">{error}</div>}
      </div>

      <section className="ai-home-section"><div className="ai-home-section-head"><div><p className="eyebrow">CONTINUE</p><h2>Your projects</h2></div><button className="btn outline" onClick={() => setShowCreate(true)}>New project</button></div>{recent.length ? <div className="ai-project-grid">{recent.map((project) => <button className="ai-project-card" key={project.id} onClick={() => onOpenProject(project)}><span className="ai-project-icon">◇</span><div><b>{project.name}</b><small>{project.building_type || 'Building project'} · {project.location || 'Location not specified'}</small></div><span className="ai-project-status">{project.status || 'In progress'}</span></button>)}</div> : <div className="ai-empty-projects"><span>◇</span><div><b>No projects yet</b><p>Start with a sentence above. AIrchitect will keep the first step simple.</p></div></div>}</section>

      {showCreate && <div className="ai-create-row"><input autoFocus aria-label="New project name" placeholder="Project name" onKeyDown={(event) => { if (event.key === 'Enter' && event.currentTarget.value.trim()) void onCreateProject(event.currentTarget.value.trim()).then(() => setShowCreate(false)); }} /><button className="btn primary" onClick={() => { const input = document.querySelector<HTMLInputElement>('[aria-label="New project name"]'); if (input?.value.trim()) void onCreateProject(input.value.trim()).then(() => setShowCreate(false)); }}>Create</button><button className="btn outline" onClick={() => setShowCreate(false)}>Cancel</button></div>}
    </main>
  </section>;
}

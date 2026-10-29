import React, { useEffect, useState } from 'react';
import ArchitectWorkspace from '../features/foundation/ArchitectWorkspace';
import AIHomeWorkspace from '../features/home/AIHomeWorkspace';
import AgentSettings from '../features/settings/AgentSettings';
import { normalizeProjectIntent, savePendingOnboarding } from '../features/home/projectOnboarding';
import { clearWorkspaceUrl } from '../state/workspaceNavigation';
import '../style.css';

const API = import.meta.env.VITE_API_BASE_URL || '/api/v1';
type Project = { id: string; name: string; building_type?: string; location?: string; status?: string; version?: string | number };

export default function App() {
  const [token, setToken] = useState(sessionStorage.getItem('token') || ''); const [orgs, setOrgs] = useState<any[]>([]); const [projects, setProjects] = useState<Project[]>([]); const [activeProject, setActiveProject] = useState<Project | null>(null); const [settings, setSettings] = useState(false); const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [register, setRegister] = useState(false); const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [name, setName] = useState(''); const [orgName, setOrgName] = useState('');
  async function request(path: string, init: RequestInit = {}) { const response = await fetch(API + path, { ...init, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers } }); const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.error?.message || data.detail?.message || data.detail || `Request failed (${response.status})`); return data; }
  async function loadWorkspace() { if (!token) return []; setBusy(true); setError(''); try { const organizations = await request('/organizations'); setOrgs(organizations); const nextProjects = organizations[0] ? await request(`/projects?organization_id=${organizations[0].id}`) : []; const projectList = nextProjects as Project[]; setProjects(projectList); const requestedProjectId = new URLSearchParams(window.location.search).get('project'); if (requestedProjectId) { const requestedProject = projectList.find((item) => item.id === requestedProjectId); if (requestedProject) setActiveProject(requestedProject); else window.history.replaceState({}, '', clearWorkspaceUrl(window.location.href)); } return projectList; } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not load workspace.'); return []; } finally { setBusy(false); } }
  useEffect(() => { void loadWorkspace(); }, [token]);
  async function auth(event: React.FormEvent) { event.preventDefault(); setBusy(true); setError(''); try { const data = await request(register ? '/auth/register' : '/auth/login', { method: 'POST', body: JSON.stringify(register ? { email, name, password, organization_name: orgName } : { email, password }) }); sessionStorage.setItem('token', data.access_token); setToken(data.access_token); setPassword(''); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Authentication failed.'); } finally { setBusy(false); } }
  async function createProject(intentOrName: string, intent?: string) {
    if (!orgs[0]) throw new Error('Create an organization before starting a project.');
    const draft = intent ? normalizeProjectIntent(intent) : { name: intentOrName, buildingType: 'commercial', location: 'Saudi Arabia', brief: '' };
    const data = await request('/projects', { method: 'POST', body: JSON.stringify({ organization_id: orgs[0].id, name: draft.name, building_type: draft.buildingType, location: draft.location }) });
    const created = (data.project || data) as Project;
    if (intent && created.id) savePendingOnboarding(created.id, draft.brief);
    const nextProjects = await loadWorkspace();
    const project = nextProjects.find((item) => item.id === created.id) || created;
    setActiveProject(project); setSettings(false);
  }
  function closeProject() { setActiveProject(null); window.history.replaceState({}, '', clearWorkspaceUrl(window.location.href)); }
  function signOut() { sessionStorage.removeItem('token'); window.history.replaceState({}, '', clearWorkspaceUrl(window.location.href)); setToken(''); setProjects([]); setOrgs([]); setActiveProject(null); setSettings(false); }

  if (!token) return <div className="auth-page"><div className="auth-aside"><div className="brand"><span className="brand-mark">N</span> NAZMAK</div><div className="auth-pitch"><div className="eyebrow">BUILDING FEASIBILITY PLATFORM</div><h1>Make the<br/>first decision<br/><em>count.</em></h1><p>A considered workspace for early-stage commercial development in Saudi Arabia.</p><div className="auth-foot">DESIGN WITH EVIDENCE&nbsp; / &nbsp;BUILD WITH CONFIDENCE</div></div></div><div className="auth-main"><form className="auth-card" onSubmit={auth}><div className="eyebrow">YOUR WORKSPACE</div><h2>{register ? 'Create your account' : 'Welcome back'}</h2><p className="muted">{register ? 'Set up your organization to begin.' : 'Sign in to continue to your projects.'}</p>{register && <><label>Full name<input required value={name} onChange={event => setName(event.target.value)} placeholder="Your name"/></label><label>Organization<input required value={orgName} onChange={event => setOrgName(event.target.value)} placeholder="Company name"/></label></>}<label>Work email<input required type="email" value={email} onChange={event => setEmail(event.target.value)} placeholder="name@company.com"/></label><label>Password<input required type="password" minLength={register ? 12 : 1} value={password} onChange={event => setPassword(event.target.value)} placeholder={register ? 'At least 12 characters' : 'Enter your password'}/></label>{error && <div className="alert" role="alert">{error}</div>}<button className="btn primary full" disabled={busy}>{busy ? 'Please wait…' : register ? 'Create account' : 'Sign in'} ↗</button><button type="button" className="text-btn" onClick={() => { setRegister(!register); setError(''); }}>{register ? 'Already have an account? Sign in' : 'New to Nazmak? Create an account'}</button></form></div></div>;
  if (activeProject) return <ArchitectWorkspace api={API} token={token} project={activeProject} onClose={closeProject} />;
  if (settings) return <div className="app-shell"><main className="main-area"><div className="content"><button className="btn outline" onClick={() => setSettings(false)}>← Back</button><AgentSettings/></div></main></div>;
  return <AIHomeWorkspace projects={projects} organizationName={orgs[0]?.name} onOpenProject={project => setActiveProject(project)} onCreateProject={createProject} onSettings={() => setSettings(true)} onSignOut={signOut} />;
}

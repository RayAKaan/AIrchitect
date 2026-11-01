import React, { useEffect, useState } from 'react';
import ArchitectWorkspace from '../features/foundation/ArchitectWorkspace';
import AIHomeWorkspace from '../features/home/AIHomeWorkspace';
import AgentSettings from '../features/settings/AgentSettings';
import OrganizationSettings from '../features/settings/OrganizationSettings';
import { normalizeProjectIntent, savePendingOnboarding } from '../features/home/projectOnboarding';
import { clearWorkspaceUrl } from '../state/workspaceNavigation';
import '../style.css';

const API = import.meta.env.VITE_API_BASE_URL || '/api/v1';
type Project = { id: string; name: string; building_type?: string; location?: string; status?: string; version?: string | number };

export default function App() {
  const [token, setToken] = useState(''); const [checkingSession, setCheckingSession] = useState(true); const [forgotPassword, setForgotPassword] = useState(false); const [verificationRequired, setVerificationRequired] = useState(false); const [verificationNotice, setVerificationNotice] = useState(''); const [recoveryMessage, setRecoveryMessage] = useState(''); const [recoveryEmail, setRecoveryEmail] = useState(''); const [newPassword, setNewPassword] = useState(''); const [verifyToken, setVerifyToken] = useState(() => new URLSearchParams(window.location.search).get('verify_token') || ''); const [resetToken, setResetToken] = useState(() => new URLSearchParams(window.location.search).get('reset_token') || ''); const [inviteToken, setInviteToken] = useState(() => new URLSearchParams(window.location.search).get('token') || ''); const [inviteNotice, setInviteNotice] = useState(''); const [orgs, setOrgs] = useState<any[]>([]); const [selectedOrganizationId, setSelectedOrganizationId] = useState(''); const [projects, setProjects] = useState<Project[]>([]); const [activeProject, setActiveProject] = useState<Project | null>(null); const [settings, setSettings] = useState(false); const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [register, setRegister] = useState(false); const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [name, setName] = useState(''); const [orgName, setOrgName] = useState('');
  function csrfCookie() { return document.cookie.split(';').map(value => value.trim()).find(value => value.startsWith('airchitect_csrf='))?.slice('airchitect_csrf='.length) || ''; }
  async function refreshAccessToken() { const csrf = csrfCookie(); const response = await fetch(API + '/auth/refresh', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRF-Token': decodeURIComponent(csrf) } : {}) }, body: '{}' }); if (!response.ok) return ''; const data = await response.json(); return data.access_token as string; }
  async function request(path: string, init: RequestInit = {}) { const send = (accessToken: string) => fetch(API + path, { ...init, credentials: 'include', headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}), ...init.headers } }); let response = await send(token); if (response.status === 401 && token && !path.startsWith('/auth/')) { const renewed = await refreshAccessToken(); if (renewed) { setToken(renewed); response = await send(renewed); } } const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.error?.message || data.detail?.message || data.detail || `Request failed (${response.status})`); return data; }
  async function loadWorkspace(preferredOrganizationId?: string) { if (!token) return []; setBusy(true); setError(''); try { const organizations = await request('/organizations'); const selectedOrganization = organizations.find((item: any) => item.id === (preferredOrganizationId || selectedOrganizationId)) || organizations[0]; const orderedOrganizations = selectedOrganization ? [selectedOrganization, ...organizations.filter((item: any) => item.id !== selectedOrganization.id)] : organizations; setOrgs(orderedOrganizations); setSelectedOrganizationId(selectedOrganization?.id || ''); const nextProjects = selectedOrganization ? await request(`/projects?organization_id=${selectedOrganization.id}`) : []; const projectList = nextProjects as Project[]; setProjects(projectList); const requestedProjectId = new URLSearchParams(window.location.search).get('project'); if (requestedProjectId) { const requestedProject = projectList.find((item) => item.id === requestedProjectId); if (requestedProject) setActiveProject(requestedProject); else window.history.replaceState({}, '', clearWorkspaceUrl(window.location.href)); } return projectList; } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not load workspace.'); return []; } finally { setBusy(false); } }
  useEffect(() => { let active = true; void refreshAccessToken().then(restored => { if (active && restored) setToken(restored); }).catch(() => {}).finally(() => { if (active) setCheckingSession(false); }); return () => { active = false; }; }, []);
  useEffect(() => {
    if (!verifyToken) return;
    let active = true;
    void fetch(API + '/auth/verify-email', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: verifyToken }),
    }).then(async response => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error?.message || data.detail || 'This verification link is invalid or expired.');
      if (active) setVerificationNotice('Your email address is verified. You can now sign in.');
    }).catch(cause => {
      if (active) setVerificationNotice(cause instanceof Error ? cause.message : 'Email verification failed.');
    }).finally(() => {
      if (active) {
        setVerifyToken('');
        const url = new URL(window.location.href); url.searchParams.delete('verify_token');
        window.history.replaceState({}, '', url.pathname + url.search + url.hash);
      }
    });
    return () => { active = false; };
  }, [verifyToken]);

  useEffect(() => { void loadWorkspace(); }, [token]);
  useEffect(() => { if (!token || !inviteToken) return; void request('/invitations/accept', { method: 'POST', body: JSON.stringify({ token: inviteToken }) }).then(result => { setInviteNotice('Organization invitation accepted.'); setInviteToken(''); window.history.replaceState({}, '', window.location.pathname + window.location.hash); void loadWorkspace(result.organization_id); }).catch(cause => setInviteNotice(cause instanceof Error ? cause.message : 'Could not accept invitation.')); }, [token, inviteToken]);
  async function auth(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setVerificationNotice('');
    try {
      const data = await request(register ? '/auth/register' : '/auth/login', {
        method: 'POST', body: JSON.stringify(register ? { email, name, password, organization_name: orgName } : { email, password }),
      });
      setPassword('');
      if (data.verification_required) {
        setVerificationRequired(true);
        setVerificationNotice(data.message || 'Check your email to verify your account.');
        setRecoveryEmail(email);
        setRegister(false);
        return;
      }
      setToken(data.access_token);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Authentication failed.';
      setError(message);
      if (message.toLowerCase().includes('verify your email')) setRecoveryEmail(email);
    } finally { setBusy(false); }
  }
  async function sendVerificationAgain() {
    setBusy(true); setRecoveryMessage('');
    try {
      const data = await request('/auth/resend-verification', { method: 'POST', body: JSON.stringify({ email: recoveryEmail || email }) });
      setRecoveryMessage(data.message || 'If the account requires verification, an email will be sent shortly.');
    } catch (cause) { setRecoveryMessage(cause instanceof Error ? cause.message : 'Could not request a verification email.'); }
    finally { setBusy(false); }
  }
  async function requestPasswordReset(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setRecoveryMessage('');
    try {
      const data = await request('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email: recoveryEmail }) });
      setRecoveryMessage(data.message || 'If an account exists for that address, password-reset instructions will be sent.');
    } catch (cause) { setRecoveryMessage(cause instanceof Error ? cause.message : 'Could not request password-reset instructions.'); }
    finally { setBusy(false); }
  }
  async function submitPasswordReset(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setRecoveryMessage('');
    try {
      await request('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token: resetToken, new_password: newPassword }) });
      setResetToken(''); setNewPassword(''); setForgotPassword(false);
      const url = new URL(window.location.href); url.searchParams.delete('reset_token');
      window.history.replaceState({}, '', url.pathname + url.search + url.hash);
      setRecoveryMessage('Your password has been reset. Sign in with your new password.');
    } catch (cause) { setRecoveryMessage(cause instanceof Error ? cause.message : 'Password reset failed.'); }
    finally { setBusy(false); }
  }
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
  async function signOut() { try { const fresh = await refreshAccessToken(); if (fresh) await fetch(API + '/auth/logout', { method: 'POST', credentials: 'include', headers: { Authorization: 'Bearer ' + fresh } }); else if (token) await request('/auth/logout', { method: 'POST' }); } catch { /* local sign-out still clears in-memory credentials */ } window.history.replaceState({}, '', clearWorkspaceUrl(window.location.href)); setToken(''); setProjects([]); setOrgs([]); setSelectedOrganizationId(''); setActiveProject(null); setSettings(false); }

  if (checkingSession) return <div className="auth-page"><div className="auth-main"><p className="muted">Restoring your secure session…</p></div></div>;
  if (!token) {
    const authCard = resetToken ? (
      <form className="auth-card" onSubmit={submitPasswordReset}>
        <div className="eyebrow">ACCOUNT SECURITY</div><h2>Reset your password</h2>
        <p className="muted">Choose a new password. The reset link is single-use and expires after 30 minutes.</p>
        <label>New password<input required type="password" minLength={12} maxLength={128} autoComplete="new-password" value={newPassword} onChange={event => setNewPassword(event.target.value)} placeholder="At least 12 characters"/></label>
        {recoveryMessage && <div className="alert" role="status">{recoveryMessage}</div>}
        <button className="btn primary full" disabled={busy}>{busy ? 'Please wait…' : 'Set new password'} ↗</button>
        <button type="button" className="text-btn" onClick={() => { setResetToken(''); setRecoveryMessage(''); const url = new URL(window.location.href); url.searchParams.delete('reset_token'); window.history.replaceState({}, '', url.pathname + url.search + url.hash); }}>Back to sign in</button>
      </form>
    ) : verificationRequired ? (
      <div className="auth-card">
        <div className="eyebrow">VERIFY YOUR EMAIL</div><h2>Check your inbox</h2>
        <p className="muted">{verificationNotice || 'A verification link has been sent to your email address.'}</p>
        <label>Work email<input type="email" value={recoveryEmail} onChange={event => setRecoveryEmail(event.target.value)} placeholder="name@company.com"/></label>
        {recoveryMessage && <div className="alert" role="status">{recoveryMessage}</div>}
        <button className="btn primary full" disabled={busy || !recoveryEmail.trim()} onClick={() => void sendVerificationAgain()}>{busy ? 'Please wait…' : 'Resend verification email'}</button>
        <button type="button" className="text-btn" onClick={() => { setVerificationRequired(false); setVerificationNotice(''); setRecoveryMessage(''); }}>Back to sign in</button>
      </div>
    ) : forgotPassword ? (
      <form className="auth-card" onSubmit={requestPasswordReset}>
        <div className="eyebrow">ACCOUNT RECOVERY</div><h2>Forgot your password?</h2>
        <p className="muted">Enter your account email. If an account exists, reset instructions will be sent.</p>
        <label>Work email<input required type="email" value={recoveryEmail} onChange={event => setRecoveryEmail(event.target.value)} placeholder="name@company.com"/></label>
        {recoveryMessage && <div className="alert" role="status">{recoveryMessage}</div>}
        <button className="btn primary full" disabled={busy}>{busy ? 'Please wait…' : 'Send reset instructions'} ↗</button>
        <button type="button" className="text-btn" onClick={() => { setForgotPassword(false); setRecoveryMessage(''); }}>Back to sign in</button>
      </form>
    ) : (
      <form className="auth-card" onSubmit={auth}>
        <div className="eyebrow">YOUR WORKSPACE</div><h2>{register ? 'Create your account' : 'Welcome back'}</h2>
        <p className="muted">{register ? 'Set up your organization to begin.' : 'Sign in to continue to your projects.'}</p>
        {verificationNotice && <div className="alert" role="status">{verificationNotice}</div>}
        {recoveryMessage && <div className="alert" role="status">{recoveryMessage}</div>}
        {register && <><label>Full name<input required value={name} onChange={event => setName(event.target.value)} placeholder="Your name"/></label><label>Organization<input required value={orgName} onChange={event => setOrgName(event.target.value)} placeholder="Company name"/></label></>}
        <label>Work email<input required type="email" value={email} onChange={event => setEmail(event.target.value)} placeholder="name@company.com" autoComplete="email"/></label>
        <label>Password<input required type="password" minLength={register ? 12 : 1} value={password} onChange={event => setPassword(event.target.value)} placeholder={register ? 'At least 12 characters' : 'Enter your password'} autoComplete={register ? 'new-password' : 'current-password'}/></label>
        {error && <div className="alert" role="alert">{error}</div>}
        {!register && error.toLowerCase().includes('verify your email') && <button type="button" className="text-btn" onClick={() => { setRecoveryEmail(email); setVerificationRequired(true); setRecoveryMessage(''); }}>Resend verification email</button>}
        <button className="btn primary full" disabled={busy}>{busy ? 'Please wait…' : register ? 'Create account' : 'Sign in'} ↗</button>
        {!register && <button type="button" className="text-btn" onClick={() => { setRecoveryEmail(email); setForgotPassword(true); setRecoveryMessage(''); setError(''); }}>Forgot password?</button>}
        <button type="button" className="text-btn" onClick={() => { setRegister(!register); setError(''); setRecoveryMessage(''); }}>{register ? 'Already have an account? Sign in' : 'New to Nazmak? Create an account'}</button>
      </form>
    );
    return <div className="auth-page"><div className="auth-aside"><div className="brand"><span className="brand-mark">N</span> NAZMAK</div><div className="auth-pitch"><div className="eyebrow">BUILDING FEASIBILITY PLATFORM</div><h1>Make the<br/>first decision<br/><em>count.</em></h1><p>A considered workspace for early-stage commercial development in Saudi Arabia.</p><div className="auth-foot">DESIGN WITH EVIDENCE&nbsp; / &nbsp;BUILD WITH CONFIDENCE</div></div></div><div className="auth-main">{authCard}</div></div>;
  }
  if (activeProject) return <ArchitectWorkspace api={API} token={token} project={activeProject} onClose={closeProject} />;
  if (settings) return <div className="app-shell"><main className="main-area"><div className="content"><button className="btn outline" onClick={() => setSettings(false)}>← Back</button>{orgs[0] && <OrganizationSettings api={API} token={token} organization={orgs[0]} />}<AgentSettings/></div></main></div>;
  return <>{inviteNotice && <div className="alert" role="status">{inviteNotice}</div>}<AIHomeWorkspace projects={projects} organizationName={orgs[0]?.name} onOpenProject={project => setActiveProject(project)} onCreateProject={createProject} onSettings={() => setSettings(true)} onSignOut={signOut} /></>;
}

import { useEffect, useState } from 'react';
import './organizationSettings.css';

type Organization = { id: string; name: string; role: string };
type Member = { user_id: string; email: string; name: string; role: string; joined_at: string };
type Invitation = { id: string; email: string; role: string; status: string; created_at: string; expires_at: string };

export default function OrganizationSettings({ api, token, organization }: { api: string; token: string; organization: Organization }) {
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('member');
  const [inviteUrl, setInviteUrl] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const canManage = organization.role === 'owner' || organization.role === 'admin';
  const headers = { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token };

  async function call(path: string, init: RequestInit = {}) {
    const response = await fetch(api + path, { ...init, credentials: 'include', headers: { ...headers, ...init.headers } });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error?.message || data.detail?.message || data.detail || ('Request failed (' + response.status + ')'));
    return data;
  }

  async function load() {
    setError('');
    try {
      const people = await call('/organizations/' + organization.id + '/members');
      setMembers(people);
      if (canManage) setInvitations(await call('/organizations/' + organization.id + '/invitations'));
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not load organization members.'); }
  }

  useEffect(() => { void load(); }, [organization.id, token]);

  async function invite(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setInviteUrl('');
    try {
      const result = await call('/organizations/' + organization.id + '/invitations', { method: 'POST', body: JSON.stringify({ email, role }) });
      setInviteUrl(window.location.origin + result.accept_path);
      setEmail(''); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not create invitation.'); }
    finally { setBusy(false); }
  }

  async function changeRole(member: Member, nextRole: string) {
    setBusy(true); setError('');
    try { await call('/organizations/' + organization.id + '/members/' + member.user_id, { method: 'PATCH', body: JSON.stringify({ role: nextRole }) }); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not update member role.'); }
    finally { setBusy(false); }
  }

  async function removeMember(member: Member) {
    if (!window.confirm('Remove ' + member.email + ' from this organization?')) return;
    setBusy(true); setError('');
    try { await call('/organizations/' + organization.id + '/members/' + member.user_id, { method: 'DELETE' }); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not remove member.'); }
    finally { setBusy(false); }
  }

  async function revokeInvite(invitation: Invitation) {
    setBusy(true); setError('');
    try { await call('/organizations/' + organization.id + '/invitations/' + invitation.id, { method: 'DELETE' }); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not revoke invitation.'); }
    finally { setBusy(false); }
  }

  return <section className="org-settings">
    <div className="org-settings-heading"><div><p className="eyebrow">ORGANIZATION</p><h2>{organization.name}</h2><p className="muted">Your role: {organization.role}</p></div><span className="org-role-pill">{organization.role}</span></div>
    {error && <div className="alert" role="alert">{error}</div>}
    {canManage && <div className="org-settings-card"><h3>Invite a teammate</h3><p className="muted">Create a single-use invitation link. The link is shown once; share it with the intended email address.</p>
      <form className="org-invite-form" onSubmit={invite}><label>Email address<input type="email" required value={email} onChange={event => setEmail(event.target.value)} placeholder="teammate@company.com" /></label><label>Role<select value={role} onChange={event => setRole(event.target.value)}><option value="member">Member</option><option value="viewer">Viewer</option>{organization.role === 'owner' && <option value="admin">Administrator</option>}</select></label><button className="btn primary" disabled={busy || !email.trim()}>Create invitation</button></form>
      {inviteUrl && <div className="org-invite-link"><span>{inviteUrl}</span><button className="btn outline small" onClick={() => void navigator.clipboard?.writeText(inviteUrl)}>Copy link</button></div>}
    </div>}
    <div className="org-settings-card"><div className="org-card-heading"><h3>Members</h3><span>{members.length}</span></div><div className="org-member-list">{members.map(member => { const manageable = canManage && member.role !== 'owner' && !(organization.role === 'admin' && member.role === 'admin'); return <div className="org-member-row" key={member.user_id}><div className="org-member-avatar">{(member.name || member.email).slice(0, 1).toUpperCase()}</div><div className="org-member-copy"><b>{member.name}</b><small>{member.email}</small></div>{manageable ? <><select aria-label={'Role for ' + member.email} value={member.role} disabled={busy} onChange={event => void changeRole(member, event.target.value)}><option value="member">Member</option><option value="viewer">Viewer</option>{organization.role === 'owner' && <option value="admin">Administrator</option>}</select><button className="btn outline small" disabled={busy} onClick={() => void removeMember(member)}>Remove</button></> : <span className="org-role-pill">{member.role}</span>}</div>; })}</div></div>
    {canManage && <div className="org-settings-card"><div className="org-card-heading"><h3>Invitations</h3><span>{invitations.filter(item => item.status === 'PENDING').length} pending</span></div><div className="org-invitation-list">{invitations.length ? invitations.map(invitation => <div className="org-invitation-row" key={invitation.id}><div><b>{invitation.email}</b><small>{invitation.role} · expires {new Date(invitation.expires_at).toLocaleDateString()}</small></div><span className={'org-invite-status ' + invitation.status.toLowerCase()}>{invitation.status}</span>{invitation.status === 'PENDING' && <button className="btn outline small" disabled={busy} onClick={() => void revokeInvite(invitation)}>Revoke</button>}</div>) : <p className="muted">No invitations yet.</p>}</div></div>}
  </section>;
}

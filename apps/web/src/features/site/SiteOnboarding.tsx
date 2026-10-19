import { useState } from 'react';

const steps = [
  ['1', 'Define the site', 'Draw a boundary. The backend validates geometry and creates the canonical revision.'],
  ['2', 'Add evidence', 'Connect approved context providers and review provenance before relying on derived facts.'],
  ['3', 'Analyze and compose', 'Run deterministic analysis, generate diagrams, then assemble a preliminary board.'],
] as const;

export default function SiteOnboarding() {
  const [open, setOpen] = useState(() => localStorage.getItem('airchitect.site-onboarding') !== 'done');
  if (!open) return null;
  return <aside className="site-onboarding" aria-label="Site workspace guide"><div className="site-onboarding-head"><div><p className="eyebrow">FIRST RUN</p><h2>Site workflow</h2></div><button className="icon-button" aria-label="Dismiss guide" onClick={() => { localStorage.setItem('airchitect.site-onboarding', 'done'); setOpen(false); }}>×</button></div><ol>{steps.map(([number, title, text]) => <li key={number}><span>{number}</span><div><strong>{title}</strong><p>{text}</p></div></li>)}</ol><button className="btn primary" onClick={() => { localStorage.setItem('airchitect.site-onboarding', 'done'); setOpen(false); }}>Got it</button></aside>;
}

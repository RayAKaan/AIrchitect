import { useEffect, useState } from 'react';

const steps = [
  ['1', 'Define the site', 'Draw a boundary. The backend validates geometry and creates the canonical revision.'],
  ['2', 'Add evidence', 'Connect approved context providers and review provenance before relying on derived facts.'],
  ['3', 'Analyze and compose', 'Run deterministic analysis, generate diagrams, then assemble a preliminary board.'],
] as const;
const templates = {
  student: { label: 'Student Site Analysis', description: 'A guided site study focused on boundary, evidence, deterministic metrics and diagrams.' },
  feasibility: { label: 'Feasibility Study', description: 'A feasibility-first workflow emphasizing constraints, site analysis, evidence and preliminary presentation.' },
  sample: { label: 'Sample Project', description: 'A safe local starter configuration for exploring the workspace before connecting live providers.' },
} as const;

type TemplateKey = keyof typeof templates;

export default function SiteOnboarding() {
  const [open, setOpen] = useState(() => localStorage.getItem('airchitect.site-onboarding') !== 'done');
  const [template, setTemplate] = useState<TemplateKey>(() => (localStorage.getItem('airchitect.site-template') as TemplateKey) || 'student');
  const [step, setStep] = useState(() => Number(localStorage.getItem('airchitect.site-step') || '1'));
  useEffect(() => { localStorage.setItem('airchitect.site-template', template); localStorage.setItem('airchitect.site-step', String(step)); }, [template, step]);
  if (!open) return <button className="onboarding-reopen" type="button" onClick={() => setOpen(true)}>Open site guide</button>;
  function dismiss() { localStorage.setItem('airchitect.site-onboarding', 'done'); setOpen(false); }
  return <aside className="site-onboarding" aria-label="Site workspace guide"><div className="site-onboarding-head"><div><p className="eyebrow">FIRST RUN</p><h2>Site workflow</h2></div><button className="icon-button" aria-label="Dismiss guide" onClick={dismiss}>×</button></div>
    <div className="onboarding-template"><label htmlFor="site-template">Start with a workflow</label><select id="site-template" value={template} onChange={event => setTemplate(event.target.value as TemplateKey)}>{Object.entries(templates).map(([key, item]) => <option key={key} value={key}>{item.label}</option>)}</select><p>{templates[template].description}</p></div>
    <ol>{steps.map(([number, title, text], index) => <li className={step === index + 1 ? 'active' : step > index + 1 ? 'complete' : ''} key={number}><span>{step > index + 1 ? '✓' : number}</span><div><strong>{title}</strong><p>{text}</p></div></li>)}</ol>
    <div className="onboarding-actions"><button className="btn outline" disabled={step <= 1} onClick={() => setStep(value => Math.max(1, value - 1))}>Back</button>{step < steps.length ? <button className="btn primary" onClick={() => setStep(value => Math.min(steps.length, value + 1))}>Next</button> : <button className="btn primary" onClick={dismiss}>Finish guide</button>}</div>
  </aside>;
}

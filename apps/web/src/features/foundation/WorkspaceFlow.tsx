import { useMemo } from 'react';

const STAGES = [
  ['Brief', 'Define intent'],
  ['World Model', 'Canonical state'],
  ['Semantic Model', 'Building semantics'],
  ['Design', 'Design alternatives'],
  ['CAD/BIM Exports', 'Production exchange'],
  ['Engineering', 'Screening'],
  ['Change Impact', 'Dependency propagation'],
  ['Release Validation', 'Release gate'],
  ['Regulatory', 'Evidence-backed checks'],
] as const;

export default function WorkspaceFlow({active, onSelect}:{active:string;onSelect:(stage:string)=>void}) {
  const index = useMemo(() => Math.max(0, STAGES.findIndex(([stage]) => stage === active)), [active]);
  return <nav className="workspace-flow" aria-label="Architectural delivery workflow">
    {STAGES.map(([stage, description], i) => <button key={stage} className={`workspace-flow-step ${i === index ? 'active' : ''} ${i < index ? 'complete' : ''}`} onClick={() => onSelect(stage)} title={description}>
      <span className="workspace-flow-index">{i < index ? '✓' : i + 1}</span><span><b>{stage}</b><small>{description}</small></span>
    </button>)}
  </nav>;
}

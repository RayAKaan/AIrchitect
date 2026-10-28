import type { ProductMode } from '../../state/productWorkspace';
import './NextActionCard.css';

type Snapshot = { brief?: any; requirements?: any[]; world_model?: any; };
type Action = { title: string; reason: string; mode: ProductMode; label: string };

export function chooseAction(mode: ProductMode, snapshot: Snapshot | null, status: string): Action {
  if (!snapshot?.brief?.raw_text) return { title: 'Write the project brief', reason: 'The source intent is the foundation for requirements, program and every downstream decision.', mode: 'Brief', label: 'Open brief' };
  if (!snapshot.requirements?.length) return { title: 'Extract requirements', reason: 'Turn the source brief into explicit, reviewable requirements before generating concepts.', mode: 'Brief', label: 'Review requirements' };
  if (mode === 'Brief' || mode === 'Explore') return { title: 'Explore concepts', reason: 'The project has enough structured intent to compare deterministic concept alternatives.', mode: 'Explore', label: 'Explore concepts' };
  if (mode === 'Design') return { title: 'Validate the direction', reason: 'Check downstream impacts before treating the current design as ready for delivery.', mode: 'Validate', label: 'Open validation' };
  if (mode === 'Validate') return { title: 'Prepare deliverables', reason: 'When the release checks are acceptable, move to the professional exchange package.', mode: 'Deliver', label: 'Open deliverables' };
  if (mode === 'Deliver') return { title: 'Review provenance', reason: 'Confirm the package is tied to the intended canonical version and evidence chain.', mode: 'Validate', label: 'Review validation' };
  if (status === 'DRAFT') return { title: 'Develop a direction', reason: 'Move from project intent into a concrete design alternative.', mode: 'Design', label: 'Open design' };
  return { title: 'Review the current decisions', reason: 'Check the canonical state and its downstream consequences before continuing.', mode: 'Validate', label: 'Open validation' };
}

export default function NextActionCard({ mode, snapshot, status, onNavigate }: { mode: ProductMode; snapshot: Snapshot | null; status: string; onNavigate: (mode: ProductMode) => void }) {
  const action = chooseAction(mode, snapshot, status);
  return <aside className="next-action-card" aria-label="Next best action"><div><p className="eyebrow">NEXT BEST STEP</p><h3>{action.title}</h3><p>{action.reason}</p></div><button className="btn primary" onClick={() => onNavigate(action.mode)}>{action.label} ↗</button></aside>;
}

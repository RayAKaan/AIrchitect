import type { ProductMode } from '../../state/productWorkspace';
import './AIExplanationPanel.css';

type Snapshot = { brief?: any; requirements?: any[]; assumptions?: any[]; world_model?: any; };

export default function AIExplanationPanel({ mode, snapshot }: { mode: ProductMode; snapshot: Snapshot | null }) {
  const requirements = snapshot?.requirements || [];
  const assumptions = snapshot?.assumptions || [];
  const unknowns = snapshot?.world_model?.unknowns || [];
  const facts = [
    snapshot?.brief?.raw_text ? 'The source brief is saved for this version.' : 'No source brief has been saved yet.',
    `${requirements.length} explicit requirement${requirements.length === 1 ? '' : 's'} are available.`,
    `${assumptions.length} assumption${assumptions.length === 1 ? '' : 's'} are recorded.`,
  ];
  const review = unknowns.length ? unknowns.slice(0, 4) : ['No unresolved world-model unknowns were reported in the current snapshot.'];
  return <section className="ai-explanation" aria-label="How AIrchitect reached the current state"><div className="ai-explanation-heading"><div><p className="eyebrow">WHY THIS STATE?</p><h3>AIrchitect's current understanding</h3><p>Facts, assumptions and unknowns are kept separate so the system does not make hidden decisions for you.</p></div><span className="explanation-mode">{mode}</span></div><div className="ai-explanation-grid"><div><b>Known</b>{facts.map((item) => <div className="explanation-item" key={item}>✓ {item}</div>)}</div><div><b>Needs attention</b>{review.map((item: string) => <div className="explanation-item" key={item}>? {item}</div>)}</div></div></section>;
}

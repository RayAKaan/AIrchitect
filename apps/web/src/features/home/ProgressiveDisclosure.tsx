import type { ProductMode } from '../../state/productWorkspace';
import './ProgressiveDisclosure.css';

const CONTROLS: Record<ProductMode, string[]> = {
  Brief: ['Requirements', 'Assumptions', 'World model', 'Provenance'],
  Site: ['Boundary geometry', 'Site intelligence', 'Revision history'],
  Explore: ['Concept generation', 'Constraint weights', 'Decision rationale'],
  Design: ['Semantic model', 'Geometry', 'Engineering screening', 'Evidence'],
  Validate: ['Change impact', 'Engineering', 'Regulatory', 'Release gate'],
  Deliver: ['DXF', 'IFC', 'Schedules', 'Quantities and cost', 'Provenance'],
};

export default function ProgressiveDisclosure({ mode, onOpenAdvanced }: { mode: ProductMode; onOpenAdvanced: () => void }) {
  return <aside className="progressive-disclosure" aria-label="Professional tools">
    <div><p className="eyebrow">OPTIONAL</p><strong>Need more control?</strong><p>Professional tools stay one step away. Nothing below changes the canonical model until you explicitly approve a supported action.</p></div>
    <div className="professional-chip-list">{CONTROLS[mode].map((control) => <span key={control}>{control}</span>)}</div>
    <button className="btn outline" onClick={onOpenAdvanced}>Open professional tools</button>
  </aside>;
}

import type { SceneNode } from './sceneContract';

type SceneInspectorProps = Readonly<{
  node: SceneNode | null;
  onClear?: () => void;
}>;

export function SceneInspector({ node, onClear }: SceneInspectorProps) {
  if (!node) {
    return <aside className="artifact-panel" aria-label="Scene inspector"><h3>Inspector</h3><p>Select an architectural element to inspect its canonical identity.</p></aside>;
  }
  return (
    <aside className="artifact-panel" aria-label="Scene inspector">
      <div className="viewer-head"><div><p className="eyebrow">CANONICAL ELEMENT</p><h3>{node.id}</h3></div><button className="btn outline" onClick={onClear}>Clear</button></div>
      <dl>
        <dt>Element type</dt><dd>{node.elementType}</dd>
        <dt>Mesh index</dt><dd>{node.meshIndex}</dd>
        <dt>Model hash</dt><dd className="hash">{node.sourceModelHash}</dd>
        <dt>Geometry hash</dt><dd className="hash">{node.geometryHash}</dd>
      </dl>
      <div className="caveats"><b>Authoritative identity</b><p>The hashes identify canonical model and derived geometry state. The viewer itself never mutates either.</p></div>
    </aside>
  );
}

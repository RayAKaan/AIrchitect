import { useMemo } from 'react';
import type { ModelScene, SceneNode, SceneView } from './sceneContract';
import { projectScene } from './sceneContract';

type Props = Readonly<{
  scene: ModelScene;
  view: SceneView;
  selectedNodeId?: string | null;
  onSelect?: (node: SceneNode) => void;
}>;

export function OrthographicSceneView({ scene, view, selectedNodeId = null, onSelect }: Props) {
  const projection = useMemo(() => projectScene(scene, view), [scene, view]);
  const width = projection.bounds.maximum[0] - projection.bounds.minimum[0];
  const height = projection.bounds.maximum[1] - projection.bounds.minimum[1];
  const span = Math.max(width, height, 1e-6);
  const padding = span * 0.06;
  const viewBox = [
    projection.bounds.minimum[0] - padding,
    -(projection.bounds.maximum[1] + padding),
    width + padding * 2 || span,
    height + padding * 2 || span,
  ].join(' ');
  const nodes = useMemo(() => new Map(scene.nodes.map(node => [node.id, node])), [scene.nodes]);

  return (
    <svg className="orthographic-scene" role="img"
      aria-label={`${view} projection of canonical architectural model`}
      viewBox={viewBox} preserveAspectRatio="xMidYMid meet" data-model-hash={scene.modelHash}>
      <rect x={projection.bounds.minimum[0] - padding}
        y={-(projection.bounds.maximum[1] + padding)}
        width={width + padding * 2 || span} height={height + padding * 2 || span}
        fill="#f6f4ef" />
      {projection.faces.map((face, index) => {
        const node = nodes.get(face.elementId);
        if (!node) return null;
        const selected = node.id === selectedNodeId;
        return <polygon key={`${face.elementId}:${index}`}
          points={face.points.map(([x, y]) => `${x},${-y}`).join(' ')}
          fill={selected ? '#b97847' : '#b7afa4'} fillOpacity={view === 'plan' ? 0.8 : 0.62}
          stroke={selected ? '#70472e' : '#625d56'} strokeWidth={span * 0.003}
          vectorEffect="non-scaling-stroke" role="button" tabIndex={0}
          aria-label={`Select ${node.elementType} ${node.id}`}
          onClick={() => onSelect?.(node)}
          onKeyDown={event => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              onSelect?.(node);
            }
          }} />;
      })}
    </svg>
  );
}

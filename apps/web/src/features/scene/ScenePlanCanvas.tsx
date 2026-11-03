import { useMemo } from 'react';
import type { ModelScene, SceneNode, Vec3 } from './sceneContract';

type Point2 = readonly [number, number];
type PlanNode = Readonly<{ node: SceneNode; points: Point2[]; baseElevation: number }>;

function cross(origin: Point2, a: Point2, b: Point2) {
  return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0]);
}

function convexHull(vertices: readonly Vec3[]): Point2[] {
  const points = [...new Map(vertices.map(([x, y]) => [`${x}:${y}`, [x, y] as const])).values()]
    .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (points.length < 3) return [];
  const lower: Point2[] = [];
  for (const point of points) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], point) <= 0) lower.pop();
    lower.push(point);
  }
  const upper: Point2[] = [];
  for (const point of [...points].reverse()) {
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], point) <= 0) upper.pop();
    upper.push(point);
  }
  lower.pop();
  upper.pop();
  return [...lower, ...upper];
}

export function sceneElevationLevels(scene: ModelScene): number[] {
  const elevations = scene.nodes.flatMap((node) => {
    const mesh = scene.meshes[node.meshIndex];
    return mesh?.vertices.length ? [Math.min(...mesh.vertices.map((point) => point[2]))] : [];
  }).sort((a, b) => a - b);
  const clusters: number[][] = [];
  for (const elevation of elevations) {
    const current = clusters[clusters.length - 1];
    if (current && Math.abs(elevation - current.reduce((sum, value) => sum + value, 0) / current.length) <= 0.5) {
      current.push(elevation);
    } else {
      clusters.push([elevation]);
    }
  }
  return clusters.map((cluster) => Number((cluster.reduce((sum, value) => sum + value, 0) / cluster.length).toFixed(3)));
}

type Props = Readonly<{
  scene: ModelScene;
  selectedNodeId: string | null;
  selectedElevation: number;
  onSelect: (node: SceneNode) => void;
}>;

export function ScenePlanCanvas({ scene, selectedNodeId, selectedElevation, onSelect }: Props) {
  const planNodes = useMemo<PlanNode[]>(() => scene.nodes.flatMap((node) => {
    const mesh = scene.meshes[node.meshIndex];
    if (!mesh?.vertices.length) return [];
    const baseElevation = Math.min(...mesh.vertices.map((point) => point[2]));
    if (Math.abs(baseElevation - selectedElevation) > 0.5) return [];
    const points = convexHull(mesh.vertices);
    return points.length >= 3 ? [{ node, points, baseElevation }] : [];
  }), [scene, selectedElevation]);

  const bounds = useMemo(() => {
    const points = planNodes.flatMap((item) => item.points);
    if (!points.length) return null;
    const xs = points.map((point) => point[0]);
    const ys = points.map((point) => point[1]);
    return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
  }, [planNodes]);

  if (!bounds) return <div className="scene-plan-empty" role="status">No canonical geometry is available at this elevation.</div>;

  const width = Math.max(bounds.maxX - bounds.minX, 0.1);
  const height = Math.max(bounds.maxY - bounds.minY, 0.1);
  const padding = Math.max(width, height) * 0.06;

  return (
    <div className="scene-plan" data-model-hash={scene.modelHash}>
      <svg viewBox={`${bounds.minX - padding} ${-bounds.maxY - padding} ${width + padding * 2} ${height + padding * 2}`} role="img" aria-label="Canonical 2D plan view">
        {planNodes.map(({ node, points }) => {
          const centerX = points.reduce((sum, point) => sum + point[0], 0) / points.length;
          const centerY = -points.reduce((sum, point) => sum + point[1], 0) / points.length;
          const selected = node.id === selectedNodeId;
          return (
            <g key={node.id} className={selected ? 'scene-plan-node selected' : 'scene-plan-node'}>
              <polygon
                points={points.map(([x, y]) => `${x},${-y}`).join(' ')}
                role="button"
                tabIndex={0}
                aria-label={`Select ${node.elementType} ${node.id}`}
                aria-pressed={selected}
                onClick={() => onSelect(node)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onSelect(node);
                  }
                }}
              />
              <text x={centerX} y={centerY} textAnchor="middle" dominantBaseline="middle">{node.elementType}</text>
            </g>
          );
        })}
      </svg>
      <div className="scene-plan-meta">
        <span>Elevation {selectedElevation.toFixed(2)} m</span>
        <span>{planNodes.length} elements</span>
        <span>Model {scene.modelHash.slice(0, 12)}</span>
      </div>
    </div>
  );
}

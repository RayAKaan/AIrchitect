import { useMemo } from 'react';

type Point3 = [number, number, number?];
type FloorPlanSpace = Readonly<{
  id: string;
  name?: string;
  level_number: number;
  area_m2?: number;
  boundary: Point3[];
}>;
type FloorPlanPayload = Readonly<{
  spaces: FloorPlanSpace[];
  layout_hash?: string;
  source_lineage?: Record<string, string>;
}>;

type Props = Readonly<{
  layout: FloorPlanPayload;
  level: number;
  selectedSpaceId: string | null;
  onSelect: (space: FloorPlanSpace) => void;
}>;

export function FloorPlanCanvas({ layout, level, selectedSpaceId, onSelect }: Props) {
  const spaces = useMemo(
    () => layout.spaces.filter((space) => space.level_number === level && space.boundary.length >= 4),
    [layout.spaces, level],
  );
  const bounds = useMemo(() => {
    const points = spaces.flatMap((space) => space.boundary)
      .filter((point) => Number.isFinite(point[0]) && Number.isFinite(point[1]));
    if (!points.length) return null;
    const xs = points.map((point) => point[0]);
    const ys = points.map((point) => point[1]);
    return {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys),
    };
  }, [spaces]);

  if (!bounds) {
    return <div className="floorplan-empty" role="status">No validated room boundaries exist for this level.</div>;
  }

  const width = Math.max(bounds.maxX - bounds.minX, 0.1);
  const height = Math.max(bounds.maxY - bounds.minY, 0.1);
  const padding = Math.max(width, height) * 0.06;

  return (
    <div className="floorplan-canvas" data-layout-hash={layout.layout_hash}>
      <svg
        role="img"
        aria-label={`Floor plan for level ${level}`}
        viewBox={`${bounds.minX - padding} ${-bounds.maxY - padding} ${width + padding * 2} ${height + padding * 2}`}
        preserveAspectRatio="xMidYMid meet"
      >
        {spaces.map((space) => {
          const points = space.boundary.map(([x, y]) => `${x},${-y}`).join(' ');
          const centerX = space.boundary.reduce((sum, point) => sum + point[0], 0) / space.boundary.length;
          const centerY = -space.boundary.reduce((sum, point) => sum + point[1], 0) / space.boundary.length;
          const selected = space.id === selectedSpaceId;
          return (
            <g key={space.id} className={selected ? 'floorplan-space selected' : 'floorplan-space'}>
              <polygon
                points={points}
                role="button"
                tabIndex={0}
                aria-label={`Select ${space.name || space.id}`}
                aria-pressed={selected}
                onClick={() => onSelect(space)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onSelect(space);
                  }
                }}
              />
              <text x={centerX} y={centerY} textAnchor="middle" dominantBaseline="middle">
                {space.name || space.id}
              </text>
              {Number.isFinite(space.area_m2) && (
                <text className="floorplan-area" x={centerX} y={centerY + 0.35} textAnchor="middle">
                  {space.area_m2?.toFixed(1)} m²
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <div className="floorplan-meta">
        <span>Level {level}</span>
        <span>{spaces.length} spaces</span>
        {layout.layout_hash && <span>Layout {layout.layout_hash.slice(0, 12)}</span>}
      </div>
    </div>
  );
}

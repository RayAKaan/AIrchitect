import { useRef, useState } from 'react';

type Point = [number, number];
type GeoJsonPolygon = { type: 'Polygon'; coordinates: Point[][] };

function parsePolygon(value: unknown): Point[] {
  if (!value || typeof value !== 'object') throw new Error('GeoJSON must be an object');
  const root = value as { type?: unknown; geometry?: unknown; coordinates?: unknown };
  const candidate = root.type === 'Feature' ? root.geometry : root;
  if (!candidate || typeof candidate !== 'object') throw new Error('GeoJSON feature has no geometry');
  const geometry = candidate as { type?: unknown; coordinates?: unknown };
  if (geometry.type !== 'Polygon' || !Array.isArray(geometry.coordinates)) throw new Error('Only Polygon GeoJSON is supported for site boundaries');
  const ring = geometry.coordinates[0];
  if (!Array.isArray(ring)) throw new Error('Polygon has no exterior ring');
  const points = ring.slice(0, -1).map((coordinate: unknown) => {
    if (!Array.isArray(coordinate) || coordinate.length < 2 || typeof coordinate[0] !== 'number' || typeof coordinate[1] !== 'number') throw new Error('Polygon coordinates must be numeric longitude/latitude pairs');
    return [coordinate[0], coordinate[1]] as Point;
  });
  if (points.length < 3) throw new Error('A site boundary requires at least three vertices');
  return points;
}

export default function SiteGeoJsonTools({ points, onImport }: { points: Point[]; onImport: (points: Point[]) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState('');
  function exportBoundary() {
    const ring = [...points, points[0]];
    const geometry: GeoJsonPolygon = { type: 'Polygon', coordinates: [ring] };
    const blob = new Blob([JSON.stringify({ type: 'Feature', properties: {}, geometry }, null, 2)], { type: 'application/geo+json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'site-boundary.geojson'; anchor.click(); URL.revokeObjectURL(url);
  }
  async function importBoundary(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; if (!file) return;
    setError('');
    try { onImport(parsePolygon(JSON.parse(await file.text()))); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not import GeoJSON'); }
    finally { event.target.value = ''; }
  }
  return <div className="site-geojson-tools" aria-label="GeoJSON boundary tools"><button type="button" className="btn" onClick={() => inputRef.current?.click()}>Import GeoJSON</button><input ref={inputRef} type="file" accept=".geojson,.json,application/geo+json,application/json" onChange={importBoundary} hidden /><button type="button" className="btn" onClick={exportBoundary} disabled={points.length < 3}>Export GeoJSON</button>{error && <p className="alert" role="alert">{error}</p>}</div>;
}

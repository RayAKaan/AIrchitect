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

function parseKml(value: string): Point[] {
  const document = new DOMParser().parseFromString(value, 'application/xml');
  if (document.querySelector('parsererror')) throw new Error('KML could not be parsed as XML');
  const polygons = Array.from(document.getElementsByTagNameNS('*', 'Polygon'));
  if (polygons.length !== 1) throw new Error('KML boundary import requires exactly one Polygon');
  const ring = polygons[0].getElementsByTagNameNS('*', 'outerBoundaryIs')[0]?.getElementsByTagNameNS('*', 'LinearRing')[0];
  const coordinates = ring?.getElementsByTagNameNS('*', 'coordinates')[0]?.textContent?.trim();
  if (!coordinates) throw new Error('KML Polygon has no outer boundary coordinates');
  const points = coordinates.split(/\s+/).map((token) => {
    const values = token.split(',');
    const longitude = Number(values[0]);
    const latitude = Number(values[1]);
    if (!Number.isFinite(longitude) || !Number.isFinite(latitude) || longitude < -180 || longitude > 180 || latitude < -90 || latitude > 90) throw new Error('KML coordinates must be numeric longitude/latitude pairs in EPSG:4326');
    return [longitude, latitude] as Point;
  });
  const first = points[0];
  const last = points[points.length - 1];
  if (points.length > 1 && first[0] === last[0] && first[1] === last[1]) points.pop();
  if (points.length < 3) throw new Error('A site boundary requires at least three KML vertices');
  return points;
}

function download(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

function kmlFor(points: Point[]): string {
  const ring = [...points, points[0]].map(([longitude, latitude]) => `${longitude},${latitude},0`).join(' ');
  return `<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>AIrchitect site boundary</name><Polygon><outerBoundaryIs><LinearRing><coordinates>${ring}</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>`;
}

export default function SiteGeoJsonTools({ points, onImport }: { points: Point[]; onImport: (points: Point[]) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState('');
  function exportBoundary() {
    const ring = [...points, points[0]];
    const geometry: GeoJsonPolygon = { type: 'Polygon', coordinates: [ring] };
    download('site-boundary.geojson', JSON.stringify({ type: 'Feature', properties: {}, geometry }, null, 2), 'application/geo+json');
  }
  function exportKml() {
    if (points.length < 3) return;
    download('site-boundary.kml', kmlFor(points), 'application/vnd.google-earth.kml+xml');
  }
  async function importBoundary(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; if (!file) return;
    setError('');
    try {
      const text = await file.text();
      const extension = file.name.toLowerCase().split('.').pop();
      onImport(extension === 'kml' ? parseKml(text) : parsePolygon(JSON.parse(text)));
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not import site boundary'); }
    finally { event.target.value = ''; }
  }
  return <div className="site-geojson-tools" aria-label="Site boundary import and export tools"><button type="button" className="btn" onClick={() => inputRef.current?.click()}>Import GeoJSON / KML</button><input ref={inputRef} type="file" accept=".geojson,.json,.kml,application/geo+json,application/json,application/vnd.google-earth.kml+xml" onChange={importBoundary} hidden /><button type="button" className="btn" onClick={exportBoundary} disabled={points.length < 3}>Export GeoJSON</button><button type="button" className="btn" onClick={exportKml} disabled={points.length < 3}>Export KML</button>{error && <p className="alert" role="alert">{error}</p>}</div>;
}

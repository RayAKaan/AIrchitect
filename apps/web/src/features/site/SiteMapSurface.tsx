import { useMemo, useRef, useState } from 'react';

type Point = [number, number];

type Props = {
  points: Point[];
  onChange: (points: Point[]) => void;
  layers?: { label: string; visible: boolean }[];
  onToggleLayer?: (index: number) => void;
};

const PAD = 48;
const WIDTH = 900;
const HEIGHT = 560;

function bounds(points: Point[]) {
  const xs = points.map(point => point[0]);
  const ys = points.map(point => point[1]);
  return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
}

export default function SiteMapSurface({ points, onChange, layers = [], onToggleLayer }: Props) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<[number, number]>([0, 0]);
  const [selected, setSelected] = useState<number | null>(null);
  const drag = useRef<{ index: number; startX: number; startY: number } | null>(null);
  const box = useMemo(() => bounds(points), [points]);
  const scaleX = (WIDTH - PAD * 2) / Math.max(box.maxX - box.minX, 0.00001);
  const scaleY = (HEIGHT - PAD * 2) / Math.max(box.maxY - box.minY, 0.00001);
  const scale = Math.min(scaleX, scaleY) * zoom;
  const project = (point: Point): Point => [WIDTH / 2 + (point[0] - (box.minX + box.maxX) / 2) * scale + pan[0], HEIGHT / 2 - (point[1] - (box.minY + box.maxY) / 2) * scale + pan[1]];
  const polygon = points.map(project).map(([x, y]) => `${x},${y}`).join(' ');

  function moveVertex(index: number, event: React.PointerEvent<SVGCircleElement>) {
    const svg = event.currentTarget.ownerSVGElement;
    if (!svg || !drag.current) return;
    const rect = svg.getBoundingClientRect();
    const dx = (event.clientX - drag.current.startX) / scale;
    const dy = -(event.clientY - drag.current.startY) / scale;
    onChange(points.map((point, i) => i === index ? [point[0] + dx, point[1] + dy] : point));
    drag.current = { index, startX: event.clientX, startY: event.clientY };
    void rect;
  }

  return <div className="site-map-surface" aria-label="Site map surface">
    <div className="map-surface-tools">
      <span className="map-source-state">BASEMAP NOT CONFIGURED · CANONICAL GEOMETRY ONLY</span>
      <div className="map-tool-group" aria-label="Map controls">
        <button type="button" className="map-tool" onClick={() => setZoom(value => Math.min(8, value * 1.25))} aria-label="Zoom in">+</button>
        <button type="button" className="map-tool" onClick={() => setZoom(value => Math.max(.25, value / 1.25))} aria-label="Zoom out">−</button>
        <button type="button" className="map-tool" onClick={() => { setZoom(1); setPan([0, 0]); }} aria-label="Reset map view">Reset</button>
      </div>
    </div>
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="site-map-svg" role="img" aria-label="Editable geospatial site boundary">
      <defs><pattern id="site-grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="currentColor" strokeOpacity=".055" /></pattern></defs>
      <rect width={WIDTH} height={HEIGHT} fill="url(#site-grid)" />
      <line x1={WIDTH - 64} y1="64" x2={WIDTH - 64} y2="96" stroke="currentColor" strokeWidth="2" />
      <path d={`M${WIDTH - 64} 56l-6 10h12z`} fill="currentColor" />
      <text x={WIDTH - 64} y="112" textAnchor="middle" fontSize="11">N</text>
      <polygon points={polygon} fill="currentColor" fillOpacity=".09" stroke="currentColor" strokeWidth="2" />
      {points.map((point, index) => { const [x, y] = project(point); return <circle key={index} cx={x} cy={y} r={selected === index ? 9 : 7} tabIndex={0} aria-label={`Boundary vertex ${index + 1}`} onClick={() => setSelected(index)} onPointerDown={event => { event.currentTarget.setPointerCapture(event.pointerId); drag.current = { index, startX: event.clientX, startY: event.clientY }; }} onPointerMove={event => moveVertex(index, event)} onPointerUp={() => { drag.current = null; }} onKeyDown={event => { const step = event.shiftKey ? 0.0001 : 0.00001; if (event.key === 'ArrowLeft') onChange(points.map((item, i) => i === index ? [item[0] - step, item[1]] : item)); if (event.key === 'ArrowRight') onChange(points.map((item, i) => i === index ? [item[0] + step, item[1]] : item)); if (event.key === 'ArrowUp') onChange(points.map((item, i) => i === index ? [item[0], item[1] + step] : item)); if (event.key === 'ArrowDown') onChange(points.map((item, i) => i === index ? [item[0], item[1] - step] : item)); }} />; })}
    </svg>
    <div className="map-surface-footer"><span>EPSG:4326 · longitude / latitude</span><span>{layers.filter(layer => layer.visible).length} visible layers</span></div>
    {layers.length > 0 && <div className="map-layer-strip" aria-label="Map layers">{layers.map((layer, index) => <label key={layer.label}><input type="checkbox" checked={layer.visible} onChange={() => onToggleLayer?.(index)} />{layer.label}</label>)}</div>}
  </div>;
}

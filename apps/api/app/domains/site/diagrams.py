from __future__ import annotations

from html import escape
from typing import Any, Literal

DiagramType = Literal["figure_ground", "movement", "land_use", "green_water", "solar"]
RUNNER_VERSION = "diagram-studio-1.0.0"


def _polygon_points(boundary: dict[str, Any]) -> str:
    ring = boundary["coordinates"][0]
    xs = [float(p[0]) for p in ring]
    ys = [float(p[1]) for p in ring]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    width = max(max_x - min_x, 1e-9)
    height = max(max_y - min_y, 1e-9)
    return " ".join(f"{40 + ((x-min_x)/width)*520:.1f},{40 + (1-(y-min_y)/height)*320:.1f}" for x, y in ring)


def _header(title: str, revision_hash: str) -> str:
    return f'<text x="40" y="28" font-family="sans-serif" font-size="16" font-weight="700">{escape(title)}</text><text x="560" y="28" text-anchor="end" font-family="monospace" font-size="9">{escape(revision_hash[:12])}…</text>'


def generate_diagram(diagram_type: DiagramType, boundary: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    metrics = analysis.get("metrics", {})
    revision_hash = str(analysis.get("site_revision_hash", ""))
    if diagram_type == "figure_ground":
        body = f'<polygon points="{_polygon_points(boundary)}" fill="none" stroke="currentColor" stroke-width="2"/><text x="40" y="390" font-family="sans-serif" font-size="12">Built coverage: {float(metrics.get("building_coverage_ratio", 0))*100:.1f}%</text>'
        title = "Figure Ground"
    elif diagram_type == "movement":
        body = f'<rect x="40" y="65" width="520" height="180" rx="12" fill="none" stroke="currentColor" stroke-opacity=".2"/><text x="60" y="110" font-family="sans-serif" font-size="28">{int(metrics.get("road_feature_count", 0))}</text><text x="60" y="132" font-family="sans-serif" font-size="11">road features</text><text x="60" y="190" font-family="sans-serif" font-size="28">{float(metrics.get("road_length_m", 0)):.1f} m</text><text x="60" y="212" font-family="sans-serif" font-size="11">road length intersecting site</text>'
        title = "Movement / Access"
    elif diagram_type == "land_use":
        items = sorted((metrics.get("land_use_counts") or {}).items())[:8]
        max_value = max([int(v) for _, v in items] or [1])
        bars = []
        for index, (label, value) in enumerate(items):
            y = 70 + index * 36; width = 300 * (int(value) / max_value)
            bars.append(f'<text x="40" y="{y+14}" font-family="sans-serif" font-size="11">{escape(str(label))}</text><rect x="180" y="{y}" width="{width:.1f}" height="20" fill="currentColor" fill-opacity=".75"/><text x="490" y="{y+14}" font-family="monospace" font-size="10">{int(value)}</text>')
        body = "".join(bars) or '<text x="40" y="100" font-family="sans-serif" font-size="12">No land-use context available.</text>'
        title = "Land Use"
    elif diagram_type == "green_water":
        green = float(metrics.get("green_area_m2", 0)); water = float(metrics.get("water_area_m2", 0)); total = max(float(metrics.get("site_area_m2", 0)), 1.0)
        body = f'<text x="40" y="90" font-family="sans-serif" font-size="28">{green:.1f} m²</text><text x="40" y="112" font-family="sans-serif" font-size="11">green context / {green/total*100:.1f}% of site</text><text x="40" y="180" font-family="sans-serif" font-size="28">{water:.1f} m²</text><text x="40" y="202" font-family="sans-serif" font-size="11">water context / {water/total*100:.1f}% of site</text>'
        title = "Green / Water"
    else:
        sectors = analysis.get("solar", {}).get("edge_orientation_counts", {})
        body = '<circle cx="300" cy="205" r="95" fill="none" stroke="currentColor" stroke-width="2"/><path d="M300 90 L312 122 L300 114 L288 122 Z" fill="currentColor"/><text x="300" y="75" text-anchor="middle" font-family="sans-serif" font-size="12">N</text>' + ''.join(f'<text x="300" y="{175 + i*20}" text-anchor="middle" font-family="sans-serif" font-size="11">{escape(k.title())}: {int(v)} boundary edges</text>' for i, (k, v) in enumerate(sectors.items()))
        title = "Solar / Orientation"
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 420" role="img" aria-label="{escape(title)}">{_header(title, revision_hash)}{body}<text x="40" y="410" font-family="sans-serif" font-size="9">Deterministic diagram · {RUNNER_VERSION} · source-bound</text></svg>'
    return {"diagram_type": diagram_type, "runner_version": RUNNER_VERSION, "site_revision_hash": revision_hash, "source_context_hash": analysis.get("source_context_hash"), "svg": svg}

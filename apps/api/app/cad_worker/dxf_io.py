"""Deterministic DXF R2000 plan-footprint export.

The DXF deliverable is a metric 2D footprint exchange: each canonical element is
written as a closed LWPOLYLINE on its own stable layer. 3D solids remain in STEP
and GLB. Canonical IDs and source-model lineage are retained as XDATA.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any, Sequence


class DxfError(ValueError):
    """Raised when a DXF footprint export cannot preserve its source geometry."""


def _safe_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value or any(ord(ch) < 32 for ch in value):
        raise DxfError(f"{field} must be a non-empty string without control characters")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise DxfError(f"{field} must be a finite number")
    return float(value)


def _layer(element_id: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_$-]", "_", element_id)[:180] or "ELEMENT"
    suffix = hashlib.sha256(element_id.encode("utf-8")).hexdigest()[:8].upper()
    return f"AI_{stem}_{suffix}"[:255]


def _pair(code: int, value: Any) -> str:
    if isinstance(value, float):
        rendered = format(value, ".9g")
    else:
        rendered = str(value)
    return f"{code}\n{rendered}\n"


def write_footprint_dxf(
    path: str,
    elements: Sequence[dict[str, Any]],
    *,
    source_model_hash: str | None = None,
) -> dict[str, Any]:
    """Write one closed metric LWPOLYLINE per canonical element footprint."""
    if not elements:
        raise DxfError("cannot write a DXF with no architectural elements")
    if source_model_hash is not None and (
        len(source_model_hash) != 64
        or any(character not in "0123456789abcdef" for character in source_model_hash.lower())
    ):
        raise DxfError("source_model_hash must be a SHA-256 hex digest")

    records = []
    seen_ids: set[str] = set()
    layers: set[str] = set()
    for index, element in enumerate(elements):
        element_id = _safe_text(element.get("id"), f"elements[{index}].id")
        if element_id in seen_ids:
            raise DxfError(f"duplicate canonical element ID: {element_id}")
        seen_ids.add(element_id)
        footprint = element.get("footprint")
        points = footprint.get("points") if isinstance(footprint, dict) else None
        if not isinstance(points, list) or len(points) < 3:
            raise DxfError(f"element {element_id} has no valid footprint")
        xy = [(_number(point[0], f"{element_id}.x"), _number(point[1], f"{element_id}.y")) for point in points]
        if len(set(xy)) < 3:
            raise DxfError(f"element {element_id} footprint has fewer than three unique vertices")
        base = _number(element.get("base_elevation_m", 0.0), f"{element_id}.base_elevation_m")
        layer = _layer(element_id)
        if layer in layers:
            raise DxfError(f"DXF layer collision for element {element_id}")
        layers.add(layer)
        records.append((element_id, layer, xy, base))

    chunks: list[str] = []
    chunks.extend([
        _pair(0, "SECTION"), _pair(2, "HEADER"),
        _pair(9, "$ACADVER"), _pair(1, "AC1015"),
        _pair(9, "$INSUNITS"), _pair(70, 6),
        _pair(9, "$MEASUREMENT"), _pair(70, 1),
        _pair(0, "ENDSEC"),
        _pair(0, "SECTION"), _pair(2, "TABLES"),
        _pair(0, "TABLE"), _pair(2, "LAYER"), _pair(70, len(layers) + 1),
        _pair(0, "LAYER"), _pair(2, "0"), _pair(70, 0), _pair(62, 7), _pair(6, "CONTINUOUS"),
    ])
    for layer in sorted(layers):
        chunks.extend([_pair(0, "LAYER"), _pair(2, layer), _pair(70, 0), _pair(62, 7), _pair(6, "CONTINUOUS")])
    chunks.extend([
        _pair(0, "ENDTAB"),
        _pair(0, "TABLE"), _pair(2, "APPID"), _pair(70, 1),
        _pair(0, "APPID"), _pair(2, "AIrchitect"), _pair(70, 0),
        _pair(0, "ENDTAB"), _pair(0, "ENDSEC"),
        _pair(0, "SECTION"), _pair(2, "ENTITIES"),
    ])
    for element_id, layer, points, elevation in records:
        chunks.extend([
            _pair(0, "LWPOLYLINE"), _pair(100, "AcDbEntity"), _pair(8, layer),
            _pair(100, "AcDbPolyline"), _pair(90, len(points)), _pair(70, 1),
            _pair(38, elevation),
        ])
        for x, y in points:
            chunks.extend([_pair(10, x), _pair(20, y)])
        chunks.extend([
            _pair(1001, "AIrchitect"),
            _pair(1000, element_id),
            _pair(1000, source_model_hash or ""),
        ])
    chunks.extend([_pair(0, "ENDSEC"), _pair(0, "EOF")])
    data = "".join(chunks).encode("ascii")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    return {
        "schema": "AC1015",
        "units": "m",
        "entity_type": "LWPOLYLINE",
        "entity_count": len(records),
        "layers": sorted(layers),
        "canonical_element_ids": sorted(seen_ids),
        "source_model_hash": source_model_hash,
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def validate_dxf(data: bytes, *, expected_element_ids: Sequence[str]) -> dict[str, Any]:
    """Validate a generated DXF's sections, units, closed polylines and XDATA IDs."""
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise DxfError("DXF must be ASCII encoded") from exc
    lines = text.splitlines()
    if len(lines) % 2:
        raise DxfError("DXF group-code stream has an incomplete pair")
    pairs = [(lines[index].strip(), lines[index + 1].strip()) for index in range(0, len(lines), 2)]
    values = [value for _code, value in pairs]
    if not values or values[-1] != "EOF":
        raise DxfError("DXF EOF marker is missing")
    if "AC1015" not in values or "$INSUNITS" not in values or "LWPOLYLINE" not in values:
        raise DxfError("DXF header or entity type is missing")
    ids: list[str] = []
    for index, (code, value) in enumerate(pairs):
        if code == "1001" and value == "AIrchitect":
            if index + 2 >= len(pairs) or pairs[index + 1][0] != "1000":
                raise DxfError("DXF canonical element XDATA is malformed")
            ids.append(pairs[index + 1][1])
    if len(ids) != len(set(ids)) or set(ids) != set(expected_element_ids):
        raise DxfError("DXF canonical element IDs do not match the source model")
    entity_count = sum(code == "0" and value == "LWPOLYLINE" for code, value in pairs)
    if entity_count != len(expected_element_ids):
        raise DxfError("DXF entity count does not match canonical element count")
    return {"status": "PASS", "schema": "AC1015", "entity_count": entity_count, "canonical_element_ids": sorted(ids)}

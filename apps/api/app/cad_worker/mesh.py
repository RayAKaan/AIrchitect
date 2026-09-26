"""glTF-binary (GLB) writer for worker-generated solids.

Phase 2's viewer fabricated boxes in the browser from numeric dimensions. That is
precisely the "browser-fabricated geometry" this phase exists to eliminate, so the
worker now tessellates real B-rep solids and ships them as GLB.

The writer is deliberately small and dependency-free. The worker virtualenv
already carries a large native surface for audit purposes, so adding a glTF
library to produce ~100 lines of output would be a poor trade. Only the subset of
glTF 2.0 needed for static, flat-shaded, per-element-coloured triangle meshes is
emitted, and the result is validated by ``test_phase5_glb.py``.

Normals are computed per triangle. Sharing vertices across faces would average
away the hard edges that make a building readable, so vertices are duplicated at
face boundaries instead.
"""

from __future__ import annotations

import json
import struct
from typing import Any, Sequence

# glTF component types
_FLOAT = 5126
_UNSIGNED_SHORT = 5123
_UNSIGNED_INT = 5125

# glTF bufferView targets
_ARRAY_BUFFER = 34962
_ELEMENT_ARRAY_BUFFER = 34963

#: 65 535 vertices is the UNSIGNED_SHORT ceiling; beyond this we widen to 32-bit.
_UNSIGNED_SHORT_MAX = 65535

Vec3 = tuple[float, float, float]


class GlbError(RuntimeError):
    """Raised when a mesh cannot be encoded as valid glTF-binary."""


def _normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    """Return the unit normal of triangle (a, b, c), or a default if degenerate."""
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = (nx * nx + ny * ny + nz * nz) ** 0.5
    if length < 1e-12:
        return (0.0, 0.0, 1.0)
    return (nx / length, ny / length, nz / length)


def _pad4(length: int) -> int:
    """Return the number of padding bytes needed to reach a 4-byte boundary."""
    return (4 - (length % 4)) % 4


class MeshPart:
    """One node's worth of geometry: a triangle soup plus a material colour."""

    __slots__ = ("name", "vertices", "indices", "color")

    def __init__(
        self,
        name: str,
        vertices: Sequence[Sequence[float]],
        indices: Sequence[Sequence[int]],
        color: Vec3,
    ) -> None:
        self.name = name
        # Constructed as explicit 3-tuples so the Vec3 type is exact. A
        # generator expression yields tuple[float, ...] of unknown length, which
        # would force casts at every use site downstream.
        normalised: list[Vec3] = []
        for vertex in vertices:
            if len(vertex) < 3:
                raise GlbError(f"{name}: vertex needs three components, got {len(vertex)}")
            normalised.append((float(vertex[0]), float(vertex[1]), float(vertex[2])))
        self.vertices = normalised
        self.indices = [tuple(int(i) for i in tri) for tri in indices]
        self.color = color

    @property
    def triangle_count(self) -> int:
        """Return the number of triangles in this part."""
        return len(self.indices)

    def explode(self) -> tuple[list[Vec3], list[Vec3], list[int]]:
        """Return per-triangle ``(positions, normals, indices)`` with matching counts.

        glTF 2.0 requires the ``NORMAL`` accessor to have the same ``count`` as
        ``POSITION``; a validator rejects a mesh where they disagree. A single
        face normal therefore forces every triangle to own its own three
        vertices, so the geometry is written non-indexed and the index buffer
        becomes the trivial sequence ``0..3n-1``.

        This is not a workaround -- it is what the hard-edge requirement already
        implied. Averaging normals across shared vertices would round off the
        corners that make a building legible, so the duplication is intentional;
        making it explicit is what keeps the file valid.
        """
        positions: list[Vec3] = []
        normals: list[Vec3] = []
        indices: list[int] = []
        for a, b, c in self.indices:
            try:
                va, vb, vc = self.vertices[a], self.vertices[b], self.vertices[c]
            except IndexError as exc:
                raise GlbError(
                    f"{self.name}: index out of range for {len(self.vertices)} vertices"
                ) from exc
            normal = _normal(va, vb, vc)
            base = len(positions)
            positions.extend((va, vb, vc))
            normals.extend((normal, normal, normal))
            indices.extend((base, base + 1, base + 2))
        return positions, normals, indices


def build_glb(parts: Sequence[MeshPart]) -> bytes:
    """Encode *parts* as a glTF-binary buffer.

    Returns the complete GLB byte string. Raises :class:`GlbError` for empty or
    inconsistently indexed input rather than emitting a file that only some
    viewers can read.
    """
    parts = [part for part in parts if part.triangle_count > 0]
    if not parts:
        raise GlbError("cannot build a GLB with no triangles")

    binary = bytearray()
    buffer_views: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []
    meshes: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    materials: list[dict[str, Any]] = []

    for part in parts:
        # Vertices are expanded per triangle so POSITION and NORMAL accessors
        # share a count, which glTF requires. See MeshPart.explode.
        positions, normals, flat_indices = part.explode()
        if len(positions) != len(normals) or len(flat_indices) != len(positions):
            raise GlbError(f"{part.name}: inconsistent attribute counts")

        position_offset = len(binary)
        binary.extend(
            struct.pack(f"<{len(positions) * 3}f", *[c for v in positions for c in v])
        )
        position_length = len(binary) - position_offset
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": position_offset,
                "byteLength": position_length,
                "target": _ARRAY_BUFFER,
            }
        )
        position_accessor = len(accessors)
        xs = [v[0] for v in positions]
        ys = [v[1] for v in positions]
        zs = [v[2] for v in positions]
        accessors.append(
            {
                "bufferView": len(buffer_views) - 1,
                "componentType": _FLOAT,
                "count": len(positions),
                "type": "VEC3",
                "min": [min(xs), min(ys), min(zs)],
                "max": [max(xs), max(ys), max(zs)],
            }
        )

        normal_offset = len(binary)
        binary.extend(struct.pack(f"<{len(normals) * 3}f", *[c for n in normals for c in n]))
        normal_length = len(binary) - normal_offset
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": normal_offset,
                "byteLength": normal_length,
                "target": _ARRAY_BUFFER,
            }
        )
        normal_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": len(buffer_views) - 1,
                "count": len(normals),
                "componentType": _FLOAT,
                "type": "VEC3",
            }
        )

        # Indices are 0..len(positions)-1 by construction, so bounding the
        # position count is sufficient to choose the index width.
        use_short = len(positions) <= _UNSIGNED_SHORT_MAX
        index_component = _UNSIGNED_SHORT if use_short else _UNSIGNED_INT
        index_format = "H" if use_short else "I"
        index_offset = len(binary)
        binary.extend(struct.pack(f"<{len(flat_indices)}{index_format}", *flat_indices))
        index_length = len(binary) - index_offset
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": index_offset,
                "byteLength": index_length,
                "target": _ELEMENT_ARRAY_BUFFER,
            }
        )
        index_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": len(buffer_views) - 1,
                "componentType": index_component,
                "count": len(flat_indices),
                "type": "SCALAR",
            }
        )

        materials.append(
            {
                "name": f"{part.name}_material",
                "doubleSided": True,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [part.color[0], part.color[1], part.color[2], 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.85,
                },
            }
        )
        meshes.append(
            {
                "name": part.name,
                "primitives": [
                    {
                        "attributes": {
                            "POSITION": position_accessor,
                            "NORMAL": normal_accessor,
                        },
                        "indices": index_accessor,
                        "material": len(materials) - 1,
                        "mode": 4,
                    }
                ],
            }
        )
        nodes.append({"mesh": len(meshes) - 1, "name": part.name})

    # GLB requires the binary chunk to be 4-byte aligned.
    binary.extend(b"\x00" * _pad4(len(binary)))

    gltf: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "AIrchitect CAD worker (OCCT tessellation)"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(binary)}],
    }

    json_bytes = json.dumps(gltf, separators=(",", ":"), sort_keys=True).encode("utf-8")
    json_bytes += b"\x20" * _pad4(len(json_bytes))  # JSON chunk pads with spaces

    total_length = 12 + 8 + len(json_bytes) + 8 + len(binary)
    out = bytearray()
    out.extend(struct.pack("<III", 0x46546C67, 2, total_length))  # 'glTF', version 2
    out.extend(struct.pack("<II", len(json_bytes), 0x4E4F534A))  # 'JSON'
    out.extend(json_bytes)
    out.extend(struct.pack("<II", len(binary), 0x004E4942))  # 'BIN\0'
    out.extend(binary)
    return bytes(out)


def validate_glb(gltf: dict[str, Any], binary: bytes) -> None:
    """Raise :class:`GlbError` unless *gltf* is a structurally valid glTF 2.0 file.

    The writer validates its own output on purpose. The bug this guards against
    -- a ``NORMAL`` accessor whose count disagrees with ``POSITION`` -- produces a
    file that Python and a lenient viewer will happily load while a conforming
    viewer rejects it, so the defect only surfaces in the browser, months later.
    Checking at write time converts a silent downstream failure into a loud
    worker error while the context is still known.
    """
    if gltf.get("asset", {}).get("version") != "2.0":
        raise GlbError("asset.version must be '2.0'")

    accessors = gltf.get("accessors") or []
    buffer_views = gltf.get("bufferViews") or []
    buffers = gltf.get("buffers") or []
    if not buffers:
        raise GlbError("GLB declares no buffer")
    if buffers[0].get("byteLength") != len(binary):
        raise GlbError(
            f"buffer byteLength {buffers[0].get('byteLength')} != binary chunk {len(binary)}"
        )

    for index, view in enumerate(buffer_views):
        offset = view.get("byteOffset", 0)
        length = view.get("byteLength", 0)
        if offset % 4:
            raise GlbError(f"bufferView {index} byteOffset {offset} is not 4-byte aligned")
        if offset + length > len(binary):
            raise GlbError(f"bufferView {index} runs past the end of the binary chunk")

    def accessor_view(index: int) -> tuple[dict[str, Any], dict[str, Any]]:
        if not 0 <= index < len(accessors):
            raise GlbError(f"accessor index {index} is out of range")
        accessor = accessors[index]
        view_index = accessor.get("bufferView")
        if view_index is None or not 0 <= view_index < len(buffer_views):
            raise GlbError(f"accessor {index} has no valid bufferView")
        return accessor, buffer_views[view_index]

    modes = {0: "POINTS", 1: "LINES", 2: "LINE_LOOP", 3: "LINE_STRIP", 4: "TRIANGLES"}
    for mesh in gltf.get("meshes") or []:
        for primitive in mesh.get("primitives") or []:
            attributes = primitive.get("attributes") or {}
            for required in ("POSITION", "NORMAL"):
                if required not in attributes:
                    raise GlbError(f"primitive is missing the {required} attribute")
            position, _ = accessor_view(attributes["POSITION"])
            normal, _ = accessor_view(attributes["NORMAL"])
            if position["count"] != normal["count"]:
                raise GlbError(
                    "POSITION and NORMAL accessor counts must match: "
                    f"{position['count']} != {normal['count']}"
                )
            if position.get("type") != "VEC3" or normal.get("type") != "VEC3":
                raise GlbError("POSITION and NORMAL must both be VEC3")
            for bound in ("min", "max"):
                if bound not in position:
                    raise GlbError(f"POSITION accessor is missing the required {bound}")
            if "indices" not in primitive:
                continue
            index_accessor, index_view = accessor_view(primitive["indices"])
            if index_accessor.get("type") != "SCALAR":
                raise GlbError("the index accessor must be SCALAR")
            # Read the component type by explicit branch rather than dict.get so
            # the lookup key is always a plain int.
            component_type = index_accessor.get("componentType")
            if component_type == 5123:
                width = 2
            elif component_type == 5125:
                width = 4
            else:
                raise GlbError(
                    f"index componentType {component_type!r} is not an unsigned integer type"
                )
            count = index_accessor["count"]
            if index_accessor.get("byteOffset", 0) + count * width > index_view["byteLength"]:
                raise GlbError("the index accessor overruns its bufferView")
            mode = primitive.get("mode", 4)
            if mode == 4 and count % 3:
                raise GlbError(f"a TRIANGLES primitive needs a multiple of 3 indices, got {count}")
            offset = index_view.get("byteOffset", 0) + index_accessor.get("byteOffset", 0)
            values = struct.unpack_from(f"<{count}{'H' if width == 2 else 'I'}", binary, offset)
            if values and max(values) >= position["count"]:
                raise GlbError(
                    f"index {max(values)} is out of range for {position['count']} vertices"
                )
            if mode not in modes:
                raise GlbError(f"unknown primitive mode {mode}")


def parse_glb(data: bytes) -> tuple[dict[str, Any], bytes]:
    """Parse a GLB into (gltf_json, binary_chunk).

    Used by the tests to prove the writer emits something structurally valid
    rather than merely plausible.
    """
    if len(data) < 12:
        raise GlbError("GLB shorter than its header")
    magic, version, length = struct.unpack("<III", data[:12])
    if magic != 0x46546C67:
        raise GlbError(f"bad GLB magic {magic:#x}")
    if version != 2:
        raise GlbError(f"unsupported GLB version {version}")
    if length != len(data):
        raise GlbError(f"GLB header length {length} != actual {len(data)}")

    offset = 12
    json_chunk: dict[str, Any] | None = None
    binary_chunk = b""
    while offset + 8 <= len(data):
        chunk_length, chunk_type = struct.unpack("<II", data[offset : offset + 8])
        body = data[offset + 8 : offset + 8 + chunk_length]
        if chunk_type == 0x4E4F534A:
            json_chunk = json.loads(body.decode("utf-8"))
        elif chunk_type == 0x004E4942:
            binary_chunk = body
        offset += 8 + chunk_length

    if json_chunk is None:
        raise GlbError("GLB has no JSON chunk")
    return json_chunk, binary_chunk

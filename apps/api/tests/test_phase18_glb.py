"""Tests for the GLB writer and its structural validator.

The Phase 2 viewer fabricated boxes in the browser; Phase 18 ships real tessellated
solids instead. These tests exist because the first version of this writer emitted
a ``NORMAL`` accessor whose count disagreed with ``POSITION``, which Python and
lenient viewers accept but a conforming glTF validator rejects. The bug would have
surfaced as an invisible or broken model in the browser, long after the geometry
pipeline reported success. ``test_position_and_normal_counts_must_match`` and
``test_validator_rejects_a_mismatched_normal_count`` pin that failure shut.
"""

import struct

import pytest

from app.cad_worker.mesh import (
    GlbError,
    MeshPart,
    build_glb,
    parse_glb,
    validate_glb,
)

SQUARE = [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 0.0, 15.0), (0.0, 0.0, 15.0)]


def quad_part(name="Tower", colour=(0.78, 0.80, 0.84)):
    """Two triangles forming one quad, with the ring's vertices shared."""
    return MeshPart(name=name, vertices=SQUARE, indices=[[0, 1, 2], [0, 2, 3]], color=colour)


def raw(parts):
    """Return the encoded GLB bytes for *parts*."""
    return build_glb(parts)


def roundtrip(parts):
    """Build, parse and validate *parts*, returning (gltf_json, binary_chunk)."""
    data = build_glb(parts)
    gltf, binary = parse_glb(data)
    validate_glb(gltf, binary)
    return gltf, binary


class TestStructuralValidity:
    def test_writer_output_passes_its_own_validator(self):
        roundtrip([quad_part()])

    def test_position_and_normal_counts_must_match(self):
        gltf, _ = roundtrip([quad_part()])
        attributes = gltf["meshes"][0]["primitives"][0]["attributes"]
        position = gltf["accessors"][attributes["POSITION"]]
        normal = gltf["accessors"][attributes["NORMAL"]]
        assert position["count"] == normal["count"]

    def test_shared_vertices_are_expanded_per_triangle(self):
        # 4 source vertices, 2 triangles -> 6 emitted vertices. A single normal
        # per triangle requires each triangle to own its vertices; sharing them
        # would average the hard edge away.
        gltf, _ = roundtrip([quad_part()])
        attributes = gltf["meshes"][0]["primitives"][0]["attributes"]
        assert gltf["accessors"][attributes["POSITION"]]["count"] == 6

    def test_position_accessor_carries_bounds(self):
        gltf, _ = roundtrip([quad_part()])
        attributes = gltf["meshes"][0]["primitives"][0]["attributes"]
        position = gltf["accessors"][attributes["POSITION"]]
        assert position["min"] == [0.0, 0.0, 0.0]
        assert position["max"] == [20.0, 0.0, 15.0]

    def test_index_buffer_is_sequential_and_in_range(self):
        gltf, binary = roundtrip([quad_part()])
        primitive = gltf["meshes"][0]["primitives"][0]
        accessor = gltf["accessors"][primitive["indices"]]
        view = gltf["bufferViews"][accessor["bufferView"]]
        assert accessor["count"] == 6
        offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        values = struct.unpack_from("<6H", binary, offset)
        assert list(values) == [0, 1, 2, 3, 4, 5]
        assert max(values) < 6

    def test_normals_point_along_the_triangle_normal(self):
        gltf, binary = roundtrip([quad_part()])
        attributes = gltf["meshes"][0]["primitives"][0]["attributes"]
        view = gltf["bufferViews"][gltf["accessors"][attributes["NORMAL"]]["bufferView"]]
        values = struct.unpack_from("<18f", binary, view["byteOffset"])
        # The quad lies in the xz plane (every y is 0). Wound as given, triangle
        # (0,0,0)->(20,0,0)->(20,0,15) has u x v = (0, -300, 0), so the face
        # normal is -Y. All six vertices share it: that is the hard edge.
        assert values[0:3] == pytest.approx((0.0, -1.0, 0.0))
        for i in range(6):
            assert values[i * 3 : i * 3 + 3] == pytest.approx((0.0, -1.0, 0.0))

    def test_buffer_views_are_four_byte_aligned(self):
        gltf, _ = roundtrip([quad_part("A"), quad_part("B")])
        for view in gltf["bufferViews"]:
            assert view.get("byteOffset", 0) % 4 == 0

    def test_every_part_becomes_its_own_node_and_material(self):
        gltf, _ = roundtrip([quad_part("Tower A"), quad_part("Core 1", (0.9, 0.62, 0.28))])
        assert [node["name"] for node in gltf["nodes"]] == ["Tower A", "Core 1"]
        assert len(gltf["materials"]) == 2
        assert gltf["materials"][1]["pbrMetallicRoughness"]["baseColorFactor"][:3] == pytest.approx(
            (0.9, 0.62, 0.28)
        )

    def test_glb_header_declares_its_true_length(self):
        data = raw([quad_part()])
        magic, version, length = struct.unpack("<III", data[:12])
        assert magic == 0x46546C67
        assert version == 2
        assert length == len(data)


class TestValidatorRejectsBadInput:
    def _gltf(self):
        gltf, binary = roundtrip([quad_part()])
        return gltf, bytearray(binary)

    def test_validator_rejects_a_mismatched_normal_count(self):
        # The exact regression this suite exists for.
        gltf, binary = self._gltf()
        attributes = gltf["meshes"][0]["primitives"][0]["attributes"]
        gltf["accessors"][attributes["NORMAL"]]["count"] = 3
        with pytest.raises(GlbError, match="counts must match"):
            validate_glb(gltf, bytes(binary))

    def test_validator_rejects_an_out_of_range_index(self):
        gltf, binary = self._gltf()
        primitive = gltf["meshes"][0]["primitives"][0]
        view = gltf["bufferViews"][gltf["accessors"][primitive["indices"]]["bufferView"]]
        offset = view["byteOffset"]
        binary[offset : offset + 2] = struct.pack("<H", 9999)
        with pytest.raises(GlbError, match="out of range"):
            validate_glb(gltf, bytes(binary))

    def test_validator_rejects_a_truncated_binary_chunk(self):
        gltf, binary = self._gltf()
        with pytest.raises(GlbError, match="binary chunk"):
            validate_glb(gltf, bytes(binary)[:-8])

    def test_validator_rejects_an_unaligned_buffer_view(self):
        gltf, binary = self._gltf()
        gltf["bufferViews"][0]["byteOffset"] = 2
        with pytest.raises(GlbError, match="aligned"):
            validate_glb(gltf, bytes(binary))

    def test_validator_rejects_position_without_bounds(self):
        gltf, binary = self._gltf()
        attributes = gltf["meshes"][0]["primitives"][0]["attributes"]
        del gltf["accessors"][attributes["POSITION"]]["min"]
        with pytest.raises(GlbError, match="min"):
            validate_glb(gltf, bytes(binary))

    def test_validator_rejects_a_bad_asset_version(self):
        gltf, binary = self._gltf()
        gltf["asset"]["version"] = "1.0"
        with pytest.raises(GlbError, match="2.0"):
            validate_glb(gltf, bytes(binary))


class TestWriterInputValidation:
    def test_empty_input_is_refused(self):
        with pytest.raises(GlbError, match="no triangles"):
            build_glb([])

    def test_parts_without_triangles_are_dropped(self):
        empty = MeshPart(name="Empty", vertices=SQUARE, indices=[], color=(1.0, 0.0, 0.0))
        with pytest.raises(GlbError, match="no triangles"):
            build_glb([empty])

    def test_out_of_range_index_is_refused(self):
        bad = MeshPart(name="Bad", vertices=SQUARE, indices=[[0, 1, 99]], color=(1.0, 0.0, 0.0))
        with pytest.raises(GlbError, match="out of range"):
            build_glb([bad])

    def test_short_vertex_is_refused(self):
        with pytest.raises(GlbError, match="three components"):
            MeshPart(name="Bad", vertices=[(0.0, 0.0)], indices=[[0, 0, 0]], color=(1.0, 0.0, 0.0))

    def test_degenerate_triangle_gets_a_default_normal(self):
        # A zero-area triangle has no meaningful normal; it must not produce NaN,
        # which would silently produce an unlit black facet in the viewer.
        flat = MeshPart(
            name="Degenerate",
            vertices=[(0.0, 0.0, 0.0)] * 3,
            indices=[[0, 1, 2]],
            color=(1.0, 0.0, 0.0),
        )
        gltf, binary = roundtrip([flat])
        attributes = gltf["meshes"][0]["primitives"][0]["attributes"]
        view = gltf["bufferViews"][gltf["accessors"][attributes["NORMAL"]]["bufferView"]]
        values = struct.unpack_from("<9f", binary, view["byteOffset"])
        assert values == (0.0, 0.0, 1.0) * 3


class TestParser:
    def test_short_buffer_is_refused(self):
        with pytest.raises(GlbError, match="header"):
            parse_glb(b"glTF")

    def test_bad_magic_is_refused(self):
        with pytest.raises(GlbError, match="magic"):
            parse_glb(struct.pack("<III", 0xDEADBEEF, 2, 12) + b"\x00" * 8)

    def test_length_disagreement_is_refused(self):
        data = raw([quad_part()])
        with pytest.raises(GlbError, match="length"):
            parse_glb(data + b"\x00")

    def test_round_trip_preserves_the_generator_string(self):
        gltf, _ = roundtrip([quad_part()])
        assert "AIrchitect" in gltf["asset"]["generator"]

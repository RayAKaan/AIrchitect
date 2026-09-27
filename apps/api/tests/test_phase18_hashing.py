"""Tests for semantic hashing of generated geometry.

The hash is what lets AIrchitect prove a regenerated artifact is the same
artifact as the one it already stored. These tests pin the three properties
that make that claim true: volatile fields cannot influence the hash, kernel
floating-point noise cannot influence the hash, and reordering a design's parts
cannot influence the hash.
"""

import math

import pytest

from app.domains.cad.hashing import (
    canonical_json,
    canonicalize,
    quantize,
    semantic_hash,
    volumes_match,
)


def geometry(**overrides):
    payload = {
        "id": "mass-1",
        "footprint": {"points": [[0.0, 0.0], [20.0, 0.0], [20.0, 15.0], [0.0, 15.0]]},
        "height_m": 24.5,
        "material_class": "conceptual_mass",
    }
    payload.update(overrides)
    return payload


class TestVolatileFieldsAreIgnored:
    def test_timestamps_do_not_change_the_hash(self):
        first = geometry(generated_at="2026-01-01T00:00:00Z", duration_seconds=1.4)
        second = geometry(generated_at="2026-09-26T11:22:33Z", duration_seconds=98.7)
        assert semantic_hash(first) == semantic_hash(second)

    def test_worker_paths_and_identifiers_do_not_change_the_hash(self):
        first = geometry(
            job_id="job-abc",
            output_dir=r"H:\.cad-tools\artifacts\job-abc",
            freecad_root=r"H:\.cad-tools\freecad-1.1.3",
            document_guid="3F2A1B4C-0000-4000-8000-000000000001",
        )
        second = geometry(
            job_id="job-xyz",
            output_dir="/tmp/other-run",
            freecad_root="/opt/freecad",
            document_guid="9E8D7C6B-1111-4222-8333-444444444444",
        )
        assert semantic_hash(first) == semantic_hash(second)

    def test_volatile_substrings_are_caught_inside_longer_names(self):
        assert semantic_hash(geometry(freecad_document_guid="a")) == semantic_hash(
            geometry(freecad_document_guid="b")
        )
        assert semantic_hash(geometry(mesh_tmp_path="a")) == semantic_hash(geometry(mesh_tmp_path="b"))

    def test_a_meaningful_field_still_changes_the_hash(self):
        # Guards against a stripping rule so broad it swallows real design data.
        assert semantic_hash(geometry(height_m=24.5)) != semantic_hash(geometry(height_m=24.6))


class TestNumericStability:
    def test_kernel_noise_below_the_quantum_does_not_change_the_hash(self):
        # OCCT 7.8.1 and 7.9.3 disagree in the last bits of a computed volume.
        assert semantic_hash(geometry(volume_m3=7350.0)) == semantic_hash(
            geometry(volume_m3=7350.0000000004)
        )

    def test_a_real_change_above_the_quantum_does_change_the_hash(self):
        assert semantic_hash(geometry(volume_m3=7350.0)) != semantic_hash(
            geometry(volume_m3=7350.01)
        )

    def test_negative_zero_folds_onto_positive_zero(self):
        # -0.0 == 0.0 in Python but serialises differently in JSON, which would
        # silently split one geometry across two hashes.
        assert canonicalize({"height_m": -0.0}) == canonicalize({"height_m": 0.0})
        assert semantic_hash(geometry(height_m=-0.0)) == semantic_hash(geometry(height_m=0.0))

    def test_quantize_normalises_negative_zero(self):
        assert quantize(-1e-12) == 0.0
        assert math.copysign(1.0, quantize(-1e-12)) > 0

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_non_finite_floats_are_rejected(self, bad):
        with pytest.raises(ValueError):
            canonicalize({"volume_m3": bad})

    def test_nan_never_reaches_the_serialised_form(self):
        with pytest.raises(ValueError):
            canonical_json({"x": math.nan})


class TestOrderIndependence:
    def test_element_order_does_not_change_the_hash(self):
        a = geometry(id="a")
        b = geometry(id="b", height_m=10.0)
        assert semantic_hash({"elements": [a, b]}) == semantic_hash({"elements": [b, a]})

    def test_footprint_point_order_still_matters(self):
        # Guards the allowlist against creeping. A ring's point order is part of
        # the geometry: reordering it defines a different shape, so two different
        # buildings must never collide onto one hash.
        square = [[0.0, 0.0], [20.0, 0.0], [20.0, 15.0], [0.0, 15.0]]
        rotated = [[20.0, 0.0], [20.0, 15.0], [0.0, 15.0], [0.0, 0.0]]
        assert semantic_hash(geometry(footprint={"points": square})) != semantic_hash(
            geometry(footprint={"points": rotated})
        )

    def test_mapping_key_order_does_not_change_the_hash(self):
        assert semantic_hash({"a": 1, "b": 2}) == semantic_hash({"b": 2, "a": 1})

    def test_set_membership_not_iteration_order_determines_the_hash(self):
        assert semantic_hash({"k": {1, 2, 3}}) == semantic_hash({"k": {3, 2, 1}})

    def test_canonical_json_is_byte_stable(self):
        text = canonical_json({"b": [1, 2], "a": {"d": 4, "c": 3}})
        assert text == '{"a":{"c":3,"d":4},"b":[1,2]}'


class TestUnicode:
    def test_equivalent_unicode_forms_hash_identically(self):
        # "Café" precomposed vs decomposed must not split an artifact in two.
        assert semantic_hash({"name": "Caf\u00e9"}) == semantic_hash({"name": "Cafe\u0301"})


class TestUnsupportedTypes:
    def test_uncanonicalisable_type_is_rejected(self):
        with pytest.raises(TypeError):
            canonicalize({"when": object()})


class TestVolumesMatch:
    def test_relative_tolerance_scales_with_the_expected_value(self):
        assert volumes_match(7350.0 * 1.004, 7350.0, 0.005)
        assert volumes_match(40000.0 * 1.004, 40000.0, 0.005)

    def test_disagreement_outside_tolerance_is_rejected(self):
        assert not volumes_match(7350.0 * 1.05, 7350.0, 0.005)

    def test_zero_expected_falls_back_to_an_absolute_comparison(self):
        assert volumes_match(0.0, 0.0, 0.005)
        assert not volumes_match(1.0, 0.0, 0.005)

    def test_non_finite_never_matches(self):
        assert not volumes_match(math.nan, 100.0, 0.5)
        assert not volumes_match(100.0, math.inf, 0.5)

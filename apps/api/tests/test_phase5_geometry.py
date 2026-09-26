"""Tests for the pure-Python geometry helpers and the worker request contract.

These exercise the parts of the CAD pipeline that need no native kernel, so they
run in the ordinary API environment. The kernel-dependent paths are covered by
``test_phase5_worker_live.py``, which skips when the worker virtualenv is absent.
"""

import pytest
from pydantic import ValidationError

from app.cad_worker import geometry as geom
from app.domains.cad.config import CadConfig
from app.domains.cad.protocol import (
    CadJobOptions,
    CadJobRequest,
    CadJobTolerances,
    MassingElement,
)

SQUARE = [(0.0, 0.0), (20.0, 0.0), (20.0, 15.0), (0.0, 15.0)]


class TestSignedArea:
    def test_counter_clockwise_ring_is_positive(self):
        assert geom.signed_area(SQUARE) == pytest.approx(300.0)

    def test_clockwise_ring_is_negative(self):
        assert geom.signed_area(list(reversed(SQUARE))) == pytest.approx(-300.0)

    def test_l_shape_area(self):
        # A 10x10 square with a 4x3 notch removed: 100 - 12 = 88.
        l_shape = [(0.0, 0.0), (10.0, 0.0), (10.0, 7.0), (6.0, 7.0), (6.0, 10.0), (0.0, 10.0)]
        assert geom.signed_area(l_shape) == pytest.approx(88.0)


class TestPerimeter:
    def test_rectangle_perimeter_includes_the_closing_edge(self):
        assert geom.perimeter(SQUARE) == pytest.approx(70.0)

    def test_degenerate_input(self):
        assert geom.perimeter([]) == 0.0
        assert geom.perimeter([(0.0, 0.0)]) == 0.0

    def test_l_shape_perimeter(self):
        l_shape = [(0.0, 0.0), (10.0, 0.0), (10.0, 7.0), (6.0, 7.0), (6.0, 10.0), (0.0, 10.0)]
        # 10 + 7 + 4 + 3 + 6 + 10
        assert geom.perimeter(l_shape) == pytest.approx(40.0)


class TestRingValidation:
    def test_clean_ring_is_not_degenerate(self):
        assert not geom.ring_is_degenerate(SQUARE)

    def test_too_few_points_is_degenerate(self):
        assert geom.ring_is_degenerate([(0.0, 0.0), (1.0, 0.0)])

    def test_zero_area_ring_is_degenerate(self):
        assert geom.ring_is_degenerate([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)])

    def test_self_intersecting_ring_is_degenerate(self):
        # A bow-tie: the two diagonals cross.
        bow_tie = [(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)]
        assert geom.ring_is_degenerate(bow_tie)

    def test_repeated_point_is_degenerate(self):
        assert geom.ring_is_degenerate([(0.0, 0.0), (0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])

    def test_concave_but_valid_ring_is_accepted(self):
        l_shape = [(0.0, 0.0), (10.0, 0.0), (10.0, 7.0), (6.0, 7.0), (6.0, 10.0), (0.0, 10.0)]
        assert not geom.ring_is_degenerate(l_shape)


class TestHelperPredicates:
    def test_is_finite_number(self):
        assert geom.is_finite_number(1.5)
        assert not geom.is_finite_number(float("nan"))
        assert not geom.is_finite_number(float("inf"))
        assert not geom.is_finite_number("1.5")

    def test_iter_flat_skips_non_numeric_entries(self):
        # Deliberately shallow: it flattens one level of a numeric collection and
        # discards anything that is not a finite number.
        assert list(geom.iter_flat([1, "two", None, 3.5, float("nan")])) == [1.0, 3.5]


class TestProtocolValidation:
    def element(self, **overrides):
        payload = {
            "id": "mass-1",
            "kind": "building_mass",
            "name": "Tower A",
            "footprint": {"points": [[0, 0], [20, 0], [20, 15], [0, 15]]},
            "base_elevation_m": 0.0,
            "height_m": 24.5,
            "material_class": "conceptual_mass",
        }
        payload.update(overrides)
        return MassingElement(**payload)

    def test_minimal_element_round_trips(self):
        element = self.element()
        assert element.kind == "building_mass"
        assert element.height_m == 24.5
        assert element.footprint.points[0] == (0.0, 0.0)

    def test_negative_height_is_rejected(self):
        with pytest.raises(ValidationError):
            self.element(height_m=-1.0)

    def test_zero_height_is_rejected(self):
        with pytest.raises(ValidationError):
            self.element(height_m=0.0)

    def test_footprint_needs_at_least_three_points(self):
        with pytest.raises(ValidationError):
            self.element(footprint={"points": [[0, 0], [1, 1]]})

    def test_empty_element_list_is_rejected(self):
        with pytest.raises(ValidationError):
            CadJobRequest(job_id="j", elements=[])

    def test_tolerances_must_be_positive(self):
        with pytest.raises(ValidationError):
            CadJobTolerances(volume_tolerance_ratio=0.0)
        with pytest.raises(ValidationError):
            CadJobTolerances(area_tolerance_ratio=-0.1)

    def test_options_field_does_not_shadow_pydantic_validate(self):
        # A field literally named "validate" overrides BaseModel.validate, which
        # pydantic defines as a classmethod. Renaming it to run_validation keeps
        # model-level validation helpers working.
        options = CadJobOptions()
        assert options.run_validation is True
        assert "validate" not in CadJobOptions.model_fields
        assert callable(CadJobOptions.validate)

    def test_request_serialises_to_plain_json_types(self):
        import json

        request = CadJobRequest(
            job_id="job-1",
            elements=[self.element()],
            sandbox_root=r"C:\artifacts",
            output_dir=r"C:\artifacts\job-1",
        )
        payload = json.loads(request.model_dump_json())
        assert payload["job_id"] == "job-1"
        assert payload["elements"][0]["kind"] == "building_mass"
        assert isinstance(payload["tolerances"]["volume_tolerance_ratio"], float)

    def test_element_count_is_capped(self):
        with pytest.raises(ValidationError):
            CadJobRequest(
                job_id="j",
                elements=[self.element(id=f"m{i}") for i in range(2001)],
                sandbox_root=r"C:\artifacts",
                output_dir=r"C:\artifacts\j",
            )


class TestCadConfig:
    def test_defaults_are_sane(self):
        config = CadConfig()
        assert config.geometry_engine == "cad_bim"
        assert config.provider == "auto"
        assert config.job_timeout_seconds > 0
        assert config.max_output_bytes > 0
        assert config.max_request_bytes <= config.max_output_bytes

    def test_freeze_prevents_post_construction_mutation(self):
        config = CadConfig()
        with pytest.raises(Exception):
            config.geometry_engine = "legacy"  # type: ignore[misc]

    def test_direct_construction_is_validated_too(self):
        # DEFAULT_CAD_CONFIG = CadConfig() bypasses from_settings, so the
        # dataclass must police itself or a bad policy reaches the worker.
        with pytest.raises(ValueError, match="timeouts must be positive"):
            CadConfig(job_timeout_seconds=0)
        with pytest.raises(ValueError, match="payload limits must be positive"):
            CadConfig(max_output_bytes=0)
        with pytest.raises(ValueError, match="deflection must be positive"):
            CadConfig(mesh_deflection_m=0.0)
        with pytest.raises(ValueError, match="must be positive"):
            CadConfig(volume_tolerance_ratio=0.0)

    def test_unknown_provider_and_engine_are_rejected(self):
        with pytest.raises(ValueError, match="provider"):
            CadConfig(provider="none")
        with pytest.raises(ValueError, match="geometry_engine"):
            CadConfig(geometry_engine="scratch")

    def test_ifc_schema_must_name_a_schema(self):
        with pytest.raises(ValueError, match="ifc_schema"):
            CadConfig(ifc_schema="gbxml")

    def test_request_limit_cannot_exceed_output_limit(self):
        with pytest.raises(ValueError, match="cannot exceed"):
            CadConfig(max_request_bytes=10, max_output_bytes=5)

    def test_legacy_engine_requires_the_legacy_escape_hatch(self):
        with pytest.raises(ValueError, match="allow_legacy_engine"):
            CadConfig(geometry_engine="legacy", allow_legacy_engine=False)

    def test_toolchain_fingerprint_excludes_paths_and_timeouts(self):
        # Two runs that differ only in where the toolchain lives, or how long it
        # was allowed, must hash to the same geometry.
        a = CadConfig(worker_venv_root="C:/a", job_timeout_seconds=10.0)
        b = CadConfig(worker_venv_root="D:/b", job_timeout_seconds=999.0)
        assert a.toolchain_fingerprint() == b.toolchain_fingerprint()

    def test_toolchain_fingerprint_tracks_geometry_affecting_settings(self):
        a = CadConfig()
        b = CadConfig(mesh_deflection_m=0.1)
        assert a.toolchain_fingerprint() != b.toolchain_fingerprint()

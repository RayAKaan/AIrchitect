"""Tests for quantities taken off a persisted solid.

The whole point of this stage is that a number in a quantity artifact can be
traced to a measurement on a B-rep, or explicitly labelled as not being one. These
tests drive the real HTTP stack over a real (fake) worker subprocess, so the
geometry, the persistence and the engineering calculation all run for real.

What is worth protecting, and why it is not obvious:

* **The design engine already had a volume.** It computed one arithmetically from
  its own parameters. If the measured path quietly reused that number, the stage
  would appear to work while changing nothing, so the central test gives the two
  different values and asserts the measured one is the one reported.
* **Two producers write GeometryArtifact rows** with different payload shapes, and
  the engineering service used to assume the legacy one. Reading a CAD row with the
  legacy accessor raises KeyError, so the shape is now chosen explicitly.
* **A quantity that cannot be measured is reported as unsupported, not estimated.**
  Roof area is the test case: the B-rep has no labelled faces, so isolating the top
  plane would mean assuming the top of the bounding box is a roof.
* **The worker is not trusted.** Its combined totals are cross-checked against its
  own per-solid rows and against the solid's bounding box.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select

from app.db.models import CadJobRun, GeometryArtifact, QuantityArtifact
from app.domains.engineering.engines import (
    MEASURED_DIVERGENCE_WARN,
    EngineeringError,
    QuantityEngine,
    RegulatoryEngine,
    StaticRulesetProvider,
    StructuralConceptEngine,
)
from app.domains.engineering.service import is_cad_geometry
# The ``api``, ``db`` and ``cad`` fixtures are auto-discovered from conftest, so they
# are not imported here: importing a fixture would shadow the name with the test
# parameter of the same name. Only the project-setup helpers are borrowed, and those
# are module-level names rather than fixture names, so they can be used directly.
from tests.test_phase18_cad_api import (
    _alternative,
    _cad_url,
    _committed_project,
)

# The fake worker's default solid: a 10 x 10 x 30 m box.
FAKE_VOLUME_M3 = 3000.0
FAKE_AREA_M2 = 1400.0


async def _measured_project(api, cad, scenario: str = "ok"):
    """Design -> CAD job -> everything the engineering calculation needs."""
    headers, org, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)
    cad.worker_with(scenario)
    generated = await api.post(
        _cad_url(project, version, alternative),
        headers=headers,
        json={"outputs": ["glb"]},
    )
    assert generated.status_code == 201, generated.text
    return headers, org, project, version, alternative, generated.json()


def _calculate(api, headers, project, version, alternative, rate_schedule_id=None):
    return api.post(
        f"/api/v1/projects/{project['id']}/versions/{version['id']}"
        f"/design/alternatives/{alternative['id']}/engineering/calculate",
        headers=headers,
        json={"rate_schedule_id": rate_schedule_id},
    )


def _by_code(quantity: dict) -> dict[str, dict[str, Any]]:
    return {item["code"]: item for item in quantity["quantities"]}


async def test_volume_is_measured_not_declared(api, cad):
    """The reported volume is the one the kernel measured, not the one the design engine declared."""
    headers, _org, project, version, alternative, _run = await _measured_project(api, cad)

    declared = float(alternative["metrics"]["building_volume_m3"])
    assert declared != FAKE_VOLUME_M3, (
        "this test is only meaningful while the design engine's analytical volume "
        f"differs from the solid's measured volume; both are {declared}"
    )

    calculated = await _calculate(api, headers, project, version, alternative)
    assert calculated.status_code == 201, calculated.text
    quantity = calculated.json()["quantity"]
    by = _by_code(quantity)

    assert by["BUILDING_VOLUME"]["value"] == FAKE_VOLUME_M3
    assert by["BUILDING_VOLUME"]["value"] != declared
    assert by["BUILDING_VOLUME"]["type"] == "EXACT_MEASURED"
    assert "B-rep" in by["BUILDING_VOLUME"]["source"]


async def test_measured_quantities_are_labelled_and_the_rest_are_not(api, cad):
    """Every quantity says where it came from, and the measured set is the B-rep's."""
    headers, _org, project, version, alternative, _run = await _measured_project(api, cad)
    quantity = (await _calculate(api, headers, project, version, alternative)).json()["quantity"]
    by = _by_code(quantity)
    provenance = quantity["measurement_provenance"]

    assert provenance["geometry_source"] == "CAD_BREP"
    assert provenance["provider"] == "occt"
    assert provenance["cad_job_run_id"]
    assert provenance["geometry_hash"]

    # Volume, surface area and topology are read off the solid.
    assert by["BUILDING_VOLUME"]["type"] == "EXACT_MEASURED"
    assert by["ENVELOPE_SURFACE_AREA"]["type"] == "EXACT_MEASURED"
    assert by["ENVELOPE_SURFACE_AREA"]["value"] == FAKE_AREA_M2
    for code in ("SOLID_COUNT", "FACE_COUNT", "EDGE_COUNT", "VERTEX_COUNT"):
        assert by[code]["type"] == "EXACT_MEASURED"
    assert by["SOLID_COUNT"]["value"] == 1
    assert by["FACE_COUNT"]["value"] == 6
    assert by["EDGE_COUNT"]["value"] == 12
    assert by["VERTEX_COUNT"]["value"] == 8

    # Programme figures are declared, and say so. Gross floor area is a rateable
    # area; the kernel measures enclosed volume, so substituting one for the other
    # would be a category error dressed as an improvement.
    assert by["GFA"]["type"] == "DECLARED_INPUT"
    assert by["GFA"]["value"] == alternative["metrics"]["gross_floor_area_m2"]
    assert by["FLOOR_COUNT"]["type"] == "DECLARED_INPUT"
    assert by["SITE_AREA"]["type"] == "DECLARED_INPUT"

    # Footprint and height are derived from the measured bounding box.
    assert by["FOOTPRINT"]["value"] == 100.0
    assert by["FOOTPRINT"]["type"] == "EXACT_DERIVED"
    assert by["BUILDING_HEIGHT"]["value"] == 30.0
    assert by["SITE_COVERAGE"]["value"] == pytest.approx(
        100.0 / float(alternative["metrics"]["site_area_m2"]), abs=1e-4
    )

    assert set(provenance["measured_quantities"]) == {
        "BUILDING_VOLUME",
        "ENVELOPE_SURFACE_AREA",
        "SOLID_COUNT",
        "FACE_COUNT",
        "EDGE_COUNT",
        "VERTEX_COUNT",
    }
    assert "GFA" in provenance["declared_quantities"]
    assert "EXTERNAL_WALL_AREA" in provenance["approximated_quantities"]
    assert "ROOF_AREA" in provenance["unsupported_quantities"]


async def test_unmeasurable_quantities_are_reported_unsupported(api, cad):
    """A solid with no labelled faces cannot yield a roof area, and must not pretend to."""
    headers, _org, project, version, alternative, _run = await _measured_project(api, cad)
    quantity = (await _calculate(api, headers, project, version, alternative)).json()["quantity"]
    by = _by_code(quantity)

    assert by["ROOF_AREA"]["value"] is None
    assert by["ROOF_AREA"]["type"] == "NOT_SUPPORTED"
    assert "no face is labelled" in by["ROOF_AREA"]["source"]
    assert "ROOF_AREA" in quantity["unknowns"]

    # The measured total is explicitly not offered as a substitute, because a
    # consumer matching on the code would otherwise treat it as one.
    assert by["ENVELOPE_SURFACE_AREA"]["value"] != by["ROOF_AREA"]["value"]
    assert "not a roof area" in by["ENVELOPE_SURFACE_AREA"]["source"]

    # The wall estimate stays an estimate, and says why it cannot be measured.
    assert by["EXTERNAL_WALL_AREA"]["type"] == "DERIVED_APPROXIMATION"
    assert by["EXTERNAL_WALL_AREA"]["uncertainty"]["lower_bound"] < by["EXTERNAL_WALL_AREA"]["value"]
    assert "no semantic face labels" in by["EXTERNAL_WALL_AREA"]["source"]


async def test_declared_versus_measured_divergence_is_reported_not_hidden(api, cad):
    """When the design engine and the kernel disagree, both numbers stay visible."""
    headers, _org, project, version, alternative, _run = await _measured_project(api, cad)
    quantity = (await _calculate(api, headers, project, version, alternative)).json()["quantity"]

    comparison = quantity["declared_vs_measured"]
    declared = float(alternative["metrics"]["building_volume_m3"])
    assert comparison["declared_m3"] == pytest.approx(declared, abs=1e-3)
    assert comparison["measured_m3"] == FAKE_VOLUME_M3
    assert comparison["authoritative"] == "measured"
    assert comparison["relative_difference"] == pytest.approx(
        abs(FAKE_VOLUME_M3 - declared) / declared, abs=1e-5
    )
    assert comparison["relative_difference"] > MEASURED_DIVERGENCE_WARN

    # The same divergence is surfaced as a warning on the validation document, so it
    # is visible whether a reader looks at the payload or at the check results.
    warning = next(
        x for x in quantity["validation"]["warnings"] if x["code"] == "DECLARED_VOLUME_DIVERGENCE"
    )
    assert warning["status"] == "WARNING"
    # A divergence is information, not a failure: the measurement is the better
    # number and refusing to report it would be the wrong trade.
    assert quantity["validation"]["valid"] is True


async def test_cad_geometry_is_preferred_over_the_legacy_ir(api, cad, db):
    """Both producers describe the alternative; the solid is the one quantities come from."""
    headers, _org, project, version, alternative, run = await _measured_project(api, cad)

    async with db() as session:
        rows = list(
            (
                await session.scalars(
                    select(GeometryArtifact).where(
                        GeometryArtifact.alternative_id == alternative["id"]
                    )
                )
            ).all()
        )
    # The alternative carries a legacy IR row from design generation plus a CAD solid.
    assert len(rows) == 2, "expected the legacy IR and the CAD solid to coexist"
    assert sum(1 for row in rows if is_cad_geometry(row)) == 1

    quantity = (await _calculate(api, headers, project, version, alternative)).json()["quantity"]
    assert quantity["measurement_provenance"]["geometry_source"] == "CAD_BREP"
    assert quantity["measurement_provenance"]["cad_job_run_id"] == run["id"]
    assert quantity["input_geometry_hash"] == next(
        row.geometry_hash for row in rows if is_cad_geometry(row)
    )


async def test_legacy_ir_path_still_derives_from_the_description(api, cad):
    """Without a CAD solid, the legacy path still works and now admits it measures nothing."""
    headers, org, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)

    quantity = (await _calculate(api, headers, project, version, alternative)).json()["quantity"]
    provenance = quantity["measurement_provenance"]

    assert provenance["geometry_source"] == "LEGACY_IR"
    assert provenance["measured_quantities"] == []
    assert "No solid was built" in provenance["notice"]
    # The analytical volume is still what the legacy path reports, and still says so.
    by = _by_code(quantity)
    assert by["BUILDING_VOLUME"]["value"] == pytest.approx(
        float(alternative["metrics"]["building_volume_m3"]), abs=1e-2
    )
    assert by["BUILDING_VOLUME"]["type"] == "EXACT_DERIVED"
    assert by["ROOF_AREA"]["type"] == "EXACT_DERIVED"
    assert "declared_vs_measured" not in quantity


async def test_geometry_validation_run_is_enforced_for_cad_solids(api, cad, db):
    """A solid whose run did not vouch for it is refused, not quantified."""
    headers, _org, project, version, alternative, run = await _measured_project(api, cad)

    async with db() as session:
        geometry = await session.scalar(
            select(GeometryArtifact).where(
                GeometryArtifact.id == run["geometry_artifact_id"]
            )
        )
        run_id = geometry.provenance_json["cad_job_run_id"]
        run_row = await session.get(CadJobRun, run_id)
        # Put the run into the state a worker that crashed after writing geometry would
        # leave behind: measurements persisted, validation not established.
        run_row.validation_json = {"valid": False, "checks": [], "errors": ["tolerance exceeded"]}
        await session.commit()

    response = await _calculate(api, headers, project, version, alternative)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "QUANTITY_SOURCE_INVALID"
    assert response.json()["error"]["context"]["validation_errors"] == ["tolerance exceeded"]

    async with db() as session:
        assert (
            await session.scalar(
                select(QuantityArtifact).where(
                    QuantityArtifact.design_alternative_id == alternative["id"]
                )
            )
            is None
        ), "an unvalidated solid must not leave a quantity artifact behind"


async def test_validation_reports_the_geometry_it_actually_read(api, cad):
    """The engineering validation run must not score a good solid as unvalidated."""
    headers, _org, project, version, alternative, _run = await _measured_project(api, cad)
    result = (await _calculate(api, headers, project, version, alternative)).json()

    geometry_check = next(
        x for x in result["validation"]["checks"] if x["code"] == "GEOMETRY_VALID"
    )
    quantity_check = next(
        x for x in result["validation"]["checks"] if x["code"] == "QUANTITY_CONSISTENCY"
    )
    assert geometry_check["status"] == "PASS"
    assert quantity_check["status"] == "PASS"
    assert result["validation"]["status"] != "BLOCKED"


async def test_worker_lying_about_its_own_totals_is_refused(api, cad):
    """A combined total that contradicts the per-solid rows it was summed from is refused."""
    headers, _org, project, version, alternative, _run = await _measured_project(
        api, cad, "inconsistent_totals"
    )

    response = await _calculate(api, headers, project, version, alternative)
    assert response.status_code == 409, response.text
    error = response.json()["error"]
    assert error["code"] == "QUANTITY_VALIDATION_FAILED"
    assert error["context"]["errors"] == ["combined_volume_matches_solids", "combined_area_matches_solids"]


async def test_volume_larger_than_its_own_bounding_box_is_refused(api, cad):
    """A solid cannot occupy more space than the box enclosing it: this catches unit errors."""
    headers, _org, project, version, alternative, _run = await _measured_project(
        api, cad, "oversized_volume"
    )

    response = await _calculate(api, headers, project, version, alternative)
    assert response.status_code == 409, response.text
    assert "volume_within_bounding_box" in response.json()["error"]["context"]["errors"]


async def test_open_shell_never_becomes_a_measurable_artifact(api, cad, db):
    """An unclosed shell is refused at the CAD boundary, so there is nothing to quantify.

    An open shell has a computable volume, which is exactly why letting one through
    would be dangerous: the number would be real and the geometry would not be. The
    worker boundary catches it, so the job fails and no geometry artifact is written
    for a calculation to be pointed at. The engineering-side check is exercised
    directly in :func:`test_an_open_shell_is_refused_by_the_engine_itself` below --
    it exists for geometry that predates the boundary check, not as the first line of
    defence.
    """
    headers, org, project, version = await _committed_project(api)
    alternative = await _alternative(api, headers, project, version)
    cad.worker_with("open_shell")

    generated = await api.post(
        _cad_url(project, version, alternative), headers=headers, json={"outputs": ["glb"]}
    )
    assert generated.status_code == 201, generated.text
    body = generated.json()
    assert body["status"] == "FAILED", f"an unclosed shell must not report a successful run: {body}"
    assert body["geometry_artifact_id"] is None

    async with db() as session:
        solids = list(
            (
                await session.scalars(
                    select(GeometryArtifact).where(
                        GeometryArtifact.alternative_id == alternative["id"]
                    )
                )
            ).all()
        )
    assert not any(is_cad_geometry(row) for row in solids), (
        "an unclosed shell must not be persisted as a geometry artifact"
    )


def test_an_open_shell_is_refused_by_the_engine_itself():
    """The engineering check is the backstop for a solid that slipped past the worker."""
    engine = QuantityEngine()
    geometry = {
        "id": "geom-1",
        "geometry_hash": "g" * 64,
        "source": "CAD_BREP",
        "provider": "occt",
        "measurements": [
            {
                "id": "mass-1",
                "volume_m3": 3000.0,
                "surface_area_m2": 1400.0,
                "bounding_box": {"min": [0, 0, 0], "max": [10, 10, 30]},
                "solid_count": 1,
                "face_count": 6,
                "edge_count": 12,
                "vertex_count": 8,
                "is_valid": True,
                "is_closed": False,
            }
        ],
        "combined_volume_m3": 3000.0,
        "combined_area_m2": 1400.0,
        "combined_bounding_box": {"min": [0, 0, 0], "max": [10, 10, 30]},
    }
    alternative = {
        "world_hash": "w" * 64,
        "design_hash": "d" * 64,
        "metrics": {"site_area_m2": 2000.0, "gross_floor_area_m2": 6000.0, "floor_count": 6},
    }
    with pytest.raises(EngineeringError) as excinfo:
        engine.calculate({}, alternative, geometry)
    assert excinfo.value.code == "QUANTITY_VALIDATION_FAILED"
    assert excinfo.value.context["errors"] == ["solids_closed"]


async def test_cost_uses_the_measured_artifact_and_records_the_rest_as_unknown(api, cad):
    """A cost estimate over a measured solid keeps GFA as a declared input, not a guess."""
    headers, org, project, version, alternative, _ = await _measured_project(api, cad)

    schedule = await api.post(
        "/api/v1/engineering/rate-schedules",
        headers=headers,
        json={
            "organization_id": org["id"],
            "name": "Conceptual allowance",
            "version": "p18-1",
            "jurisdiction": "Riyadh",
            "currency": "SAR",
            "source_reference": "Conceptual budget study dated 2026-09-01",
            "source_type": "USER_PROVIDED",
            "effective_date": "2026-09-01",
            "entries": [
                {
                    "item_code": "GFA_ALLOWANCE",
                    "category": "Other",
                    "description": "User conceptual GFA allowance",
                    "quantity_code": "GFA",
                    "unit": "m2",
                    "rate": 1000,
                    "source_reference": "Conceptual budget study dated 2026-09-01",
                    "effective_date": "2026-09-01",
                    "confidence": "USER_DECLARED",
                },
                {
                    "item_code": "ROOF_ALLOWANCE",
                    "category": "Other",
                    "description": "Roof area allowance",
                    "quantity_code": "ROOF_AREA",
                    "unit": "m2",
                    "rate": 250,
                    "source_reference": "Conceptual budget study dated 2026-09-01",
                    "effective_date": "2026-09-01",
                    "confidence": "USER_DECLARED",
                },
            ],
        },
    )
    assert schedule.status_code == 201, schedule.text

    calculated = await _calculate(
        api, headers, project, version, alternative, rate_schedule_id=schedule.json()["id"]
    )
    assert calculated.status_code == 201, calculated.text
    cost = calculated.json()["cost"]

    lines = {line["item_code"]: line for line in cost["breakdown"]}
    assert lines["GFA_ALLOWANCE"]["quantity"] == alternative["metrics"]["gross_floor_area_m2"]
    # The rate exists but the quantity does not, so the line is an explicit unknown
    # rather than a zero-cost item that would quietly understate the estimate.
    assert "ROOF_ALLOWANCE" not in lines
    assert any(x["item_code"] == "ROOF_ALLOWANCE" for x in cost["unknowns"])


class TestEngineInIsolation:
    """Unit-level checks on the parts that do not need the HTTP stack."""

    def test_ir_source_is_required_for_the_legacy_path(self):
        with pytest.raises(KeyError):
            QuantityEngine().calculate({}, {}, {"source": "CAD_BREP"})

    def test_missing_bounding_box_is_an_explicit_refusal(self):
        geometry = {
            "source": "CAD_BREP",
            "geometry_hash": "h",
            "measurements": [],
            "combined_volume_m3": 10.0,
            "combined_area_m2": 20.0,
            "combined_bounding_box": None,
        }
        with pytest.raises(EngineeringError) as caught:
            QuantityEngine().calculate({}, {"world_hash": "w", "design_hash": "d"}, geometry)
        assert caught.value.code == "QUANTITY_SOURCE_INVALID"
        assert "bounding box" in caught.value.message

    def test_declared_input_absent_reads_as_unknown_not_zero(self):
        """No metrics means no declared programme figures, and zero would be a lie."""
        geometry = {
            "source": "CAD_BREP",
            "geometry_hash": "h",
            "measurements": [
                {
                    "id": "m1",
                    "volume_m3": 100.0,
                    "surface_area_m2": 60.0,
                    "solid_count": 1,
                    "face_count": 6,
                    "edge_count": 12,
                    "vertex_count": 8,
                    "is_valid": True,
                    "is_closed": True,
                }
            ],
            "combined_volume_m3": 100.0,
            "combined_area_m2": 60.0,
            "combined_bounding_box": {"min": [0.0, 0.0, 0.0], "max": [5.0, 5.0, 4.0]},
        }
        out = QuantityEngine().calculate({}, {"world_hash": "w", "design_hash": "d"}, geometry)
        by = _by_code(out)
        assert by["GFA"]["value"] is None
        assert by["GFA"]["type"] == "DECLARED_INPUT"
        assert by["SITE_COVERAGE"]["value"] is None
        assert by["OPEN_SITE_AREA"]["value"] is None
        absent = {
            x["quantity_code"]
            for x in out["validation"]["warnings"]
            if x["code"] == "DECLARED_INPUT_ABSENT"
        }
        assert absent == {"GFA", "FLOOR_COUNT", "SITE_AREA"}
        # A missing declaration is the programme's omission, not a fault in the solid,
        # so it warns rather than failing the whole calculation.
        assert out["validation"]["valid"] is True
        # The measured values are still reported: absent declarations do not
        # invalidate what the kernel actually measured.
        assert by["BUILDING_VOLUME"]["value"] == 100.0
        assert by["FOOTPRINT"]["value"] == 25.0
        assert by["BUILDING_HEIGHT"]["value"] == 4.0


class TestConsumerAdaptation:
    """Structural and regulatory consumers now read the quantity artifact.

    They used to read the geometry description directly, which only worked while
    every geometry was a parametric description. Over a solid there is no mass,
    no floor plate and no grid to read, so the values come from the quantity
    artifact -- that is where each value carries the label saying whether it was
    measured on a solid or declared by the programme.
    """

    def test_structural_concept_reads_measured_height_and_declared_floors(self):
        """Over a solid the height is measured-derived and the storey count is declared."""
        engine = StructuralConceptEngine()
        geometry = {
            "id": "geom-1",
            "geometry_hash": "g" * 64,
            "source": "CAD_BREP",
            "provider": "occt",
            "measurements": [
                {
                    "id": "m1",
                    "volume_m3": 3000.0,
                    "surface_area_m2": 1400.0,
                    "bounding_box": {"min": [0, 0, 0], "max": [10, 10, 30]},
                    "solid_count": 1,
                    "face_count": 6,
                    "edge_count": 12,
                    "vertex_count": 8,
                    "is_valid": True,
                    "is_closed": True,
                }
            ],
            "combined_volume_m3": 3000.0,
            "combined_area_m2": 1400.0,
            "combined_bounding_box": {"min": [0, 0, 0], "max": [10, 10, 30]},
        }
        quantity = {
            "quantity_hash": "q" * 64,
            "measurement_provenance": {"geometry_source": "CAD_BREP"},
            "quantities": [
                {"code": "BUILDING_HEIGHT", "value": 30.0, "type": "EXACT_DERIVED", "source": "axis-aligned bounding box of the measured solid(s)"},
                {"code": "FLOOR_COUNT", "value": 6.0, "type": "DECLARED_INPUT", "source": "DesignAlternative.key_metrics_json.floor_count"},
                {"code": "FOOTPRINT", "value": 100.0, "type": "EXACT_DERIVED", "source": "plan area of the axis-aligned bounding box of the measured solid"},
            ],
        }
        out = engine.calculate({}, {"world_hash": "w", "design_hash": "d", "metrics": {"floor_count": 6}, "parameters": {}}, geometry, quantity)
        assert out["structural_system"] == "RC_FRAME"
        assert out["input_basis"]["geometry_source"] == "CAD_BREP"
        # Height comes from the quantity artifact (measured bbox) with type EXACT_DERIVED
        assert out["input_basis"]["inputs"]["height"]["type"] == "EXACT_DERIVED"
        assert out["input_basis"]["inputs"]["height"]["basis"] == "QUANTITY_ARTIFACT"
        # Floors come from the quantity artifact (declared)
        assert out["input_basis"]["inputs"]["floor_count"]["type"] == "DECLARED_INPUT"
        assert out["input_basis"]["inputs"]["floor_count"]["basis"] == "QUANTITY_ARTIFACT"
        # No grid on a solid
        assert out["grid"]["status"] == "UNKNOWN"
        assert "structural_grid" not in out["input_basis"]["inputs"]
        # Warning about missing grid
        assert any(w["code"] == "STRUCTURAL_GRID_UNKNOWN" for w in out["warnings"])

    def test_regulatory_evaluation_uses_measured_height_over_declared(self):
        """A height limit is evaluated against the measured height, not the declared one."""
        engine = RegulatoryEngine(StaticRulesetProvider({
            "id": "test-rules",
            "jurisdiction": "TEST",
            "authority": "Test",
            "version": "1",
            "effective_date": "2026-01-01",
            "source_type": "VERIFIED_EXTERNAL",
            "source_reference": "test",
            "authoritative": True,
            "rules": [{"code": "H", "title": "Height limit", "parameter": "building_height_m",
                       "operator": "lte", "threshold": 25, "unit": "m",
                       "source_reference": "r1", "effective_date": "2026-01-01"}],
        }))
        geometry = {
            "geometry_hash": "g" * 64,
            "source": "CAD_BREP",
            "combined_bounding_box": {"min": [0, 0, 0], "max": [10, 10, 30]},
        }
        # Declared height is 20, but measured height (in quantity) is 30 -> should FAIL
        quantity = {
            "quantities": [
                {"code": "BUILDING_HEIGHT", "value": 30.0, "type": "EXACT_DERIVED", "source": "measured bbox"},
                {"code": "SITE_COVERAGE", "value": 0.5, "type": "EXACT_DERIVED", "source": "measured footprint / declared site"},
                {"code": "FLOOR_COUNT", "value": 6.0, "type": "DECLARED_INPUT", "source": "declared"},
            ],
        }
        out = engine.calculate(
            {"site": {"location": {"country": "TEST"}}, "building": {"use": "commercial"}},
            {"world_hash": "w", "design_hash": "d", "metrics": {"building_height_m": 20.0}, "parameters": {}},
            geometry, quantity
        )
        result = next(r for r in out["results"] if r["rule_code"] == "H")
        assert result["status"] == "FAIL"
        # The observed value should be the measured 30, not the declared 20
        assert result["observed"] == 30.0
        # The basis should point at the quantity artifact
        assert result["observed_basis"]["basis"] == "QUANTITY_ARTIFACT"
        assert result["observed_basis"]["code"] == "BUILDING_HEIGHT"
        assert result["observed_basis"]["type"] == "EXACT_DERIVED"

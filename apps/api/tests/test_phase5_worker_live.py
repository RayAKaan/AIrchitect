"""Live end-to-end tests against the real CAD toolchain.

These run the actual worker virtualenv, the real OCCT kernel and the real
IfcOpenShell. They are skipped, not failed, when the toolchain is absent, so the
ordinary API test run stays fast and does not require a 400 MB FreeCAD install --
but on a machine that has it, the pipeline is verified rather than assumed.

The invariants asserted here are the ones the Phase 5 report has to stand behind:
a solid is real, measurements agree with closed-form geometry, the two independent
kernels agree with each other, and every artifact is a structurally valid file.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
WORKER_VENV = Path(os.environ.get("CAD_WORKER_VENV", r"H:\.cad-tools\worker-venv"))
FREECAD_ROOT = Path(
    os.environ.get(
        "CAD_FREECAD_ROOT",
        r"H:\.cad-tools\freecad-1.1.3\FreeCAD_1.1.3-Windows-x86_64-py311",
    )
)

WORKER_PYTHON = WORKER_VENV / "Scripts" / "python.exe"
FREECAD_CMD = FREECAD_ROOT / "bin" / "freecadcmd.exe"

needs_worker = pytest.mark.skipif(
    not WORKER_PYTHON.is_file(),
    reason=f"CAD worker virtualenv not present at {WORKER_VENV}",
)
needs_freecad = pytest.mark.skipif(
    not FREECAD_CMD.is_file(),
    reason=f"FreeCAD console executable not present at {FREECAD_CMD}",
)

# An L-shaped footprint: a 20x15 rectangle with a 6x5 notch removed from one
# corner, so the ring is concave and the volume is not a product of two numbers.
L_FOOTPRINT = [(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (12.0, 10.0), (12.0, 15.0), (0.0, 15.0)]
L_AREA = 20.0 * 15.0 - 8.0 * 5.0  # 300 - 40 = 260 m2
L_PERIMETER = 20.0 + 10.0 + 8.0 + 5.0 + 12.0 + 15.0  # 70 m
L_HEIGHT = 24.5

EXPECTED_VOLUME = L_AREA * L_HEIGHT  # 6370.0 m3
EXPECTED_SURFACE_AREA = 2.0 * L_AREA + L_PERIMETER * L_HEIGHT  # 2235.0 m2


def job(elements=None, **overrides):
    """Build a worker request document."""
    payload = {
        "schema_version": "1.0",
        "job_id": "test-job",
        "project_name": "Test Tower",
        "elements": elements
        or [
            {
                "id": "mass-1",
                "kind": "building_mass",
                "name": "Tower A",
                "footprint": {"points": [list(p) for p in L_FOOTPRINT]},
                "base_elevation_m": 0.0,
                "height_m": L_HEIGHT,
                "material_class": "conceptual_mass",
            }
        ],
        "tolerances": {
            "volume_tolerance_ratio": 0.005,
            "area_tolerance_ratio": 0.005,
            "linear_tolerance_m": 0.01,
        },
        "options": {
            "write_fcstd": False,
            "write_step": True,
            "write_ifc": True,
            "write_glb": True,
            "run_validation": True,
            "ifc_schema": "IFC4",
        },
        "mesh_deflection_m": 0.05,
        "mesh_angular_deflection_rad": 0.35,
    }
    payload.update(overrides)
    return payload


def run_worker(request, tmp_path, *args, expect_failure=False, timeout=900):
    """Run the worker as a subprocess and return the parsed response document.

    With *expect_failure*, an ``error`` response is returned instead of failing
    the test, so rejection paths can be asserted on directly.
    """
    run = _run_worker_process(request, tmp_path, *args, timeout=timeout)
    response = run.response
    if response.get("status") == "error":
        if expect_failure:
            return response
        pytest.fail(
            f"worker failed: {response.get('error_code')}: {response.get('message')}\n"
            f"{response.get('detail', '')}"
        )
    if expect_failure:
        pytest.fail(f"expected the worker to reject this request, but it succeeded: {response}")
    assert run.returncode == 0, run.stderr[-2000:]
    return run


def run_capabilities(*args, timeout=300):
    """Ask the worker what it can do.

    ``--capabilities`` reports on stdout and exits without reading a request or
    writing a response file, so it cannot go through run_worker().
    """
    completed = subprocess.run(
        [str(WORKER_PYTHON), "-m", "app.cad_worker.main", "--capabilities", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=worker_env(),
        cwd=str(API_ROOT),
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    return json.loads(completed.stdout.strip().splitlines()[-1])


def worker_env():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(API_ROOT)
    return env


class WorkerRun:
    """A worker response plus the directory its artifacts were written to.

    Proxies item access to the response so tests read as if run_worker()
    returned the document directly, while artifact-on-disk assertions can still
    reach the real files.
    """

    def __init__(self, response, out_dir, returncode, stderr):
        self.response = response
        self.out_dir = out_dir
        self.returncode = returncode
        self.stderr = stderr

    def __getitem__(self, key):
        return self.response[key]

    def __contains__(self, key):
        return key in self.response

    def get(self, key, default=None):
        return self.response.get(key, default)

    def artifact_bytes(self, artifact):
        return (self.out_dir / artifact["filename"]).read_bytes()


def _run_worker_process(request, tmp_path, *args, timeout=900):
    request = dict(request)
    out_dir = tmp_path / "out"
    # setdefault, not assignment: several tests deliberately supply a hostile
    # output_dir to prove the worker refuses it.
    request.setdefault("output_dir", str(out_dir))
    request.setdefault("sandbox_root", str(tmp_path))
    out_dir.mkdir(parents=True, exist_ok=True)

    request_path = tmp_path / "request.json"
    response_path = tmp_path / "response.json"
    # No BOM: utf-8-sig on the worker's side tolerates one, but writing plain
    # UTF-8 keeps the fixture identical to what the API would emit.
    request_path.write_text(json.dumps(request), encoding="utf-8")

    completed = subprocess.run(
        [
            str(WORKER_PYTHON),
            "-m",
            "app.cad_worker.main",
            str(request_path),
            str(response_path),
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=worker_env(),
        cwd=str(API_ROOT),
        check=False,
    )
    assert response_path.is_file(), (
        f"the worker produced no response (exit {completed.returncode})\n"
        f"stdout: {completed.stdout[-2000:]}\nstderr: {completed.stderr[-2000:]}"
    )
    response = json.loads(response_path.read_text(encoding="utf-8"))
    return WorkerRun(response, out_dir, completed.returncode, completed.stderr)


@needs_worker
class TestWorkerCapabilities:
    def test_reports_the_real_toolchain(self):
        report = run_capabilities()
        assert report["schema_version"] == "1.0"
        assert report["occt"]["available"] is True
        assert report["occt"]["occt_version"].startswith("7.")
        assert report["ifc"]["available"] is True
        assert report["ifc"]["version"].startswith("0.8")
        assert report["glb"]["available"] is True

    def test_freecad_is_reported_when_its_root_is_given(self):
        report = run_capabilities("--freecad-root", str(FREECAD_ROOT))
        if FREECAD_CMD.is_file():
            assert report["freecad"]["available"] is True
            assert report["freecad"]["version"].startswith("1.1")

    def test_capabilities_degrade_instead_of_raising(self):
        # A missing optional dependency must be reported, not raised: the API
        # uses this to decide which provider to route a job to.
        report = run_capabilities(
            "--freecad-root", str(API_ROOT / ".nonexistent-freecad-root")
        )
        assert report["freecad"]["available"] is False
        assert report["freecad"]["error"]
        # A broken FreeCAD must not take OCCT down with it.
        assert report["occt"]["available"] is True


@needs_worker
class TestOcctProvider:
    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory):
        return run_worker(job(), tmp_path_factory.mktemp("occt"), "--provider", "occt")

    def test_job_succeeds_and_validates(self, result):
        assert result["status"] == "ok"
        assert result["provider"]["provider"] == "occt"
        assert result["validation"]["valid"] is True
        assert result["validation"]["errors"] == []

    def test_measured_volume_matches_closed_form(self, result):
        measurement = result["measurements"][0]
        assert measurement["volume_m3"] == pytest.approx(EXPECTED_VOLUME, rel=1e-6)
        assert measurement["volume_relative_error"] < 1e-9

    def test_measured_area_matches_closed_form(self, result):
        # Volume alone is a weak check: a solid can enclose the right volume with
        # the wrong faces. Surface area pins the perimeter independently.
        measurement = result["measurements"][0]
        assert measurement["surface_area_m2"] == pytest.approx(EXPECTED_SURFACE_AREA, rel=1e-6)
        assert measurement["area_relative_error"] < 1e-9

    def test_solid_is_a_single_valid_closed_shell(self, result):
        measurement = result["measurements"][0]
        assert measurement["is_valid"] is True
        assert measurement["is_closed"] is True
        assert measurement["solid_count"] == 1
        # A closed prism over a 6-vertex ring has 6 side faces plus 2 caps.
        assert measurement["face_count"] == 8

    def test_bounding_box_covers_the_footprint(self, result):
        box = result["measurements"][0]["bounding_box"]
        assert box["min"] == pytest.approx([0.0, 0.0, 0.0], abs=1e-6)
        assert box["max"] == pytest.approx([20.0, 15.0, L_HEIGHT], abs=1e-6)

    def test_combined_totals_match_the_single_element(self, result):
        assert result["combined_volume_m3"] == pytest.approx(EXPECTED_VOLUME, rel=1e-6)

    def test_step_artifact_is_written_and_non_trivial(self, result):
        step = next(a for a in result["artifacts"] if a["kind"] == "step")
        assert step["byte_size"] > 1000
        assert step["sha256"]
        assert step["filename"].endswith(".step")

    def test_glb_artifact_is_written_and_non_trivial(self, result):
        glb = next(a for a in result["artifacts"] if a["kind"] == "glb")
        assert glb["byte_size"] > 100
        assert glb["sha256"]

    def test_every_artifact_hash_is_the_real_file_hash(self, result):
        import hashlib

        # The API trusts these digests to decide whether a cached artifact can
        # be reused, so a digest that does not match the bytes on disk would
        # silently poison every downstream reconciliation.
        for artifact in result["artifacts"]:
            data = result.artifact_bytes(artifact)
            assert hashlib.sha256(data).hexdigest() == artifact["sha256"]
            assert len(data) == artifact["byte_size"]

    def test_response_stays_within_the_declared_output_budget(self, result):
        assert len(json.dumps(result.response)) < 67_108_864


@needs_worker
class TestIfcRoundTrip:
    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory):
        return run_worker(job(), tmp_path_factory.mktemp("ifc"), "--provider", "occt")

    def test_ifc_is_written(self, result):
        assert result["ifc_summary"]["schema"] == "IFC4"
        assert result["ifc_summary"]["bytes"] > 0

    def test_spatial_structure_survives_the_round_trip(self, result):
        counts = result["ifc_summary"]["inspection"]["entity_counts"]
        assert counts["IfcProject"] == 1
        assert counts["IfcSite"] == 1
        assert counts["IfcBuilding"] == 1
        assert counts["IfcBuildingStorey"] == 1

    def test_building_mass_is_a_swept_solid(self, result):
        counts = result["ifc_summary"]["inspection"]["entity_counts"]
        assert counts["IfcBuildingElementProxy"] == 1
        assert counts["IfcExtrudedAreaSolid"] == 1
        assert counts["IfcArbitraryClosedProfileDef"] == 1

    def test_predefined_type_is_a_valid_ifc4_enum(self, result):
        # "BUILDING_ELEMENT_PROXY" is not a member of
        # IfcBuildingElementProxyTypeEnum and writing it raises at export time.
        masses = result["ifc_summary"]["masses"]
        assert masses[0]["predefined_type"] == "ELEMENT"

    def test_semantic_classification_travels_in_a_property_set(self, result):
        masses = result["ifc_summary"]["masses"]
        assert masses[0]["classification"] == "Building Mass"
        assert "Pset_AIrchitectElement" in result["ifc_summary"]["inspection"]["property_sets"]

    def test_reopened_file_declares_the_schema(self, result):
        inspection = result["ifc_summary"]["inspection"]
        assert inspection["schema"] == "IFC4"
        assert inspection["ifcopenshell_version"].startswith("0.8")


@needs_worker
class TestMultiElementAndElevation:
    def test_base_elevation_shifts_the_solid_without_changing_its_volume(self, tmp_path):
        elements = [
            {
                "id": "mass-1",
                "kind": "building_mass",
                "name": "Tower",
                "footprint": {"points": [list(p) for p in L_FOOTPRINT]},
                "base_elevation_m": 12.5,
                "height_m": L_HEIGHT,
                "material_class": "conceptual_mass",
            }
        ]
        result = run_worker(job(elements=elements), tmp_path, "--provider", "occt")
        measurement = result["measurements"][0]
        assert measurement["volume_m3"] == pytest.approx(EXPECTED_VOLUME, rel=1e-6)
        assert measurement["bounding_box"]["min"][2] == pytest.approx(12.5, abs=1e-6)
        assert measurement["bounding_box"]["max"][2] == pytest.approx(12.5 + L_HEIGHT, abs=1e-6)

    def test_multiple_elements_are_measured_independently(self, tmp_path):
        elements = []
        for index in range(3):
            elements.append(
                {
                    "id": f"mass-{index}",
                    "kind": "building_mass",
                    "name": f"Tower {index}",
                    "footprint": {"points": [list(p) for p in L_FOOTPRINT]},
                    "base_elevation_m": 0.0,
                    "height_m": 10.0 + index,
                    "material_class": "conceptual_mass",
                }
            )
        result = run_worker(job(elements=elements), tmp_path, "--provider", "occt")
        assert len(result["measurements"]) == 3
        assert result["combined_volume_m3"] == pytest.approx(
            sum(L_AREA * (10.0 + i) for i in range(3)), rel=1e-9
        )

    def test_repeated_regeneration_is_byte_identical(self, tmp_path):
        # The semantic hash is what proves a regenerated artifact is the same
        # artifact; that requires the geometry itself to be deterministic.
        first = run_worker(job(), tmp_path / "a", "--provider", "occt")
        second = run_worker(job(), tmp_path / "b", "--provider", "occt")
        assert first["measurements"][0]["volume_m3"] == second["measurements"][0]["volume_m3"]


@needs_worker
class TestRequestRejection:
    def test_self_intersecting_footprint_is_rejected(self, tmp_path):
        elements = [
            {
                "id": "bow-tie",
                "kind": "building_mass",
                "name": "Bow Tie",
                "footprint": {"points": [[0, 0], [10, 10], [10, 0], [0, 10]]},
                "base_elevation_m": 0.0,
                "height_m": 10.0,
                "material_class": "conceptual_mass",
            }
        ]
        response = run_worker(
            job(elements=elements), tmp_path, "--provider", "occt", expect_failure=True
        )
        assert response["error_code"] in {"GeometryError", "RequestError"}
        assert "degenerate" in response["message"].lower() or "self-intersect" in response["message"].lower()

    def test_output_dir_outside_the_sandbox_is_refused(self, tmp_path):
        response = run_worker(
            job(output_dir=r"C:\Windows\Temp\escape", sandbox_root=str(tmp_path)),
            tmp_path,
            "--provider",
            "occt",
            expect_failure=True,
        )
        assert response["status"] == "error"
        assert response["error_code"] == "output_dir_escape"

    def test_negative_height_is_refused(self, tmp_path):
        elements = [
            {
                "id": "bad",
                "kind": "building_mass",
                "name": "Bad",
                "footprint": {"points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
                "base_elevation_m": 0.0,
                "height_m": -5.0,
                "material_class": "conceptual_mass",
            }
        ]
        response = run_worker(job(elements=elements), tmp_path, "--provider", "occt", expect_failure=True)
        assert response["status"] == "error"


@needs_worker
@needs_freecad
class TestFreecadProvider:
    """FreeCAD and the worker's own OCCT are independent implementations.

    When they agree on a building's volume, that is materially stronger evidence
    of a real solid than either kernel's self-report.
    """

    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory):
        # write_fcstd=True so the native FCStd document is exercised, not just
        # the STEP/GLB/IFC exports it can produce.
        return run_worker(
            job(options={"write_fcstd": True}),
            tmp_path_factory.mktemp("freecad"),
            "--provider",
            "freecad",
            "--freecad-root",
            str(FREECAD_ROOT),
        )

    def test_job_succeeds_through_freecad(self, result):
        assert result["status"] == "ok"
        assert result["validation"]["valid"] is True
        assert result["provider"]["freecad_version"].startswith("1.1")

    def test_freecad_agrees_with_closed_form(self, result):
        measurement = result["measurements"][0]
        assert measurement["volume_m3"] == pytest.approx(EXPECTED_VOLUME, rel=1e-6)

    def test_freecad_writes_its_native_document(self, result):
        kinds = {a["kind"] for a in result["artifacts"]}
        assert "freecad_document" in kinds
        document = next(a for a in result["artifacts"] if a["kind"] == "freecad_document")
        assert document["byte_size"] > 1000
        # A .FCStd is a zip; anything else means FreeCAD wrote the wrong thing.
        assert result.artifact_bytes(document)[:2] == b"PK"

    def test_freecad_also_produces_step_and_glb(self, result):
        kinds = {a["kind"] for a in result["artifacts"]}
        assert {"step", "glb", "ifc"} <= kinds

    def test_both_kernels_agree(self, tmp_path):
        occt = run_worker(job(), tmp_path / "occt", "--provider", "occt")
        freecad = run_worker(
            job(),
            tmp_path / "fc",
            "--provider",
            "freecad",
            "--freecad-root",
            str(FREECAD_ROOT),
        )
        assert occt["combined_volume_m3"] == pytest.approx(
            freecad["combined_volume_m3"], rel=1e-4
        )

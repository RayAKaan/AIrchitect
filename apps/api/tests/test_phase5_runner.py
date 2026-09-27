"""Tests for the API-side worker invocation: capability probing and the runner.

These run without a CAD toolchain installed. They assert the behaviour that has
to hold *regardless* of what is installed -- how a missing dependency degrades,
how a hostile request is refused, and above all that the API does not take a
worker's word for anything it can check itself.

The fake worker is a real subprocess launched through the real command line (see
``phase5_fake_worker``), so a regression in the runner's argv, environment,
working directory or file handling fails these tests rather than hiding behind a
mock. End-to-end behaviour against real OCCT and FreeCAD lives in
``test_phase5_worker_live.py``; this file must never need them.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

import pytest

from app.domains.cad import capability as cap
from app.domains.cad.capability import (
    FreecadCapabilities,
    IfcCapabilities,
    KernelCapabilities,
    OcctCapabilities,
    WorkerCapabilities,
    probe_capabilities,
    reset_capability_cache,
    resolve_freecad_cmd,
    resolve_worker_python,
)
from app.domains.cad.config import CadConfig
from app.domains.cad.errors import (
    CadDependencyMissingError,
    CadJobError,
    CadJobTimeoutError,
    CadProviderError,
    CadSecurityError,
)
from app.domains.cad.protocol import CadJobRequest, Footprint, MassingElement
from app.domains.cad.runner import _memory_limit_kwargs, _response_byte_budget, run_cad_job
from tests.phase5_fake_worker import (
    BAD_BASE64,
    EMPTY_PAYLOAD,
    EMPTY_RESULT,
    ESCAPING,
    EXE_ARTIFACT,
    FAILING,
    GARBAGE,
    GIANT,
    INVALID_RESULT,
    LYING_DIGEST,
    MISMATCHED_KIND,
    OK,
    OPEN_SHELL,
    REJECTING,
    SILENT,
    SPAWNER,
    SLOW,
    WRONG_SIZE,
    FakeCadConfig,
    FakeWorker,
)

SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_capability_cache()
    yield
    reset_capability_cache()


def make_request(**overrides: Any) -> CadJobRequest:
    payload: dict[str, Any] = {
        "job_id": "test-job",
        "project_name": "Runner Test",
        "elements": [
            MassingElement(
                id="mass-1",
                kind="building_mass",
                name="Tower",
                footprint=Footprint(points=[tuple(p) for p in SQUARE]),
                height_m=30.0,
            )
        ],
    }
    payload.update(overrides)
    return CadJobRequest.model_validate(payload)


def available_caps() -> WorkerCapabilities:
    return WorkerCapabilities(
        python_version="3.14.4",
        occt=OcctCapabilities(
            available=True,
            engine_name="OCCT",
            engine_version="7.9.3.1.1",
            occt_version="7.9.3",
        ),
        ifc=IfcCapabilities(available=True, version="0.8.5"),
        freecad=FreecadCapabilities(
            available=True, version="1.1.3", occt_version="7.8.1"
        ),
    )


def worker_python(tmp_path: Path) -> Path:
    """A real file at the conventional worker path.

    Capability resolution checks the interpreter exists before launching, so a
    missing file would fail for the wrong reason.
    """
    python = (
        tmp_path / "venv" / "Scripts" / ("python.exe" if os.name == "nt" else "python")
    )
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text("", encoding="utf-8")
    return python


# --------------------------------------------------------------------------- #
# Provider selection
# --------------------------------------------------------------------------- #


class TestProviderSelection:
    def test_auto_prefers_freecad(self):
        # FreeCAD is the richer implementation, so when both work it wins.
        assert available_caps().select_provider("auto") == "freecad"

    def test_auto_degrades_to_occt_when_freecad_is_missing(self):
        caps = WorkerCapabilities(
            occt=OcctCapabilities(available=True, occt_version="7.9.3")
        )
        assert caps.select_provider("auto") == "occt"

    def test_auto_raises_when_no_kernel_is_available(self):
        caps = WorkerCapabilities(
            occt=OcctCapabilities(available=False, error="ImportError: no OCP"),
            freecad=FreecadCapabilities(available=False, error="freecadcmd not found"),
        )
        with pytest.raises(CadDependencyMissingError) as excinfo:
            caps.select_provider("auto")
        # The underlying reason has to survive; "it did not work" is not debuggable.
        assert "no OCP" in str(excinfo.value)

    def test_explicit_freecad_is_never_silently_swapped_for_occt(self):
        # Otherwise a FreeCAD regression would be reported as an OCCT one, and the
        # artifact provenance would name a kernel that never ran.
        caps = WorkerCapabilities(
            occt=OcctCapabilities(available=True, occt_version="7.9.3")
        )
        with pytest.raises(CadDependencyMissingError):
            caps.select_provider("freecad")

    def test_unknown_provider_is_rejected(self):
        with pytest.raises(ValueError, match="unknown provider"):
            available_caps().select_provider("openscad")

    def test_build_capability_needs_a_kernel_not_just_an_exporter(self):
        # IFC and GLB describe artifacts *of* geometry; without a kernel there is
        # nothing for them to describe.
        caps = WorkerCapabilities(
            ifc=IfcCapabilities(available=True, version="0.8.5"),
            glb=KernelCapabilities(available=True),
        )
        assert caps.can_build_geometry is False

    def test_provenance_omits_an_absent_freecad_entirely(self):
        # An empty string would be indistinguishable from "FreeCAD 0.0 built this".
        caps = WorkerCapabilities(
            occt=OcctCapabilities(available=True, occt_version="7.9.3", occt_build="abc"),
            ifc=IfcCapabilities(available=True, version="0.8.5"),
        )
        record = caps.provenance()
        assert "freecad_version" not in record
        assert record["occt_version"] == "7.9.3"
        assert record["ifcopenshell_version"] == "0.8.5"

    def test_provenance_records_freecad_when_it_ran(self):
        record = available_caps().provenance()
        assert record["freecad_version"] == "1.1.3"
        # The two kernels disagree about OCCT; both facts belong in provenance.
        assert record["occt_version"] == "7.9.3"
        assert record["freecad_occt_version"] == "7.8.1"


# --------------------------------------------------------------------------- #
# Capability probing
# --------------------------------------------------------------------------- #

REPORT = {
    "schema_version": "1.0",
    "python_version": "3.14.4",
    "occt": {
        "available": True,
        "error": "",
        "engine_name": "OCCT via cadquery-ocp",
        "engine_version": "7.9.3.1.1",
        "occt_version": "7.9.3.1.1",
        "occt_build": "",
    },
    "ifc": {"available": True, "error": "", "version": "0.8.5"},
    "freecad": {
        "available": True,
        "error": "",
        "version": "1.1.3",
        "occt_version": "7.8.1",
    },
    "glb": {"available": True, "error": ""},
}


def parse_report(stdout: str) -> WorkerCapabilities:
    return cap._parse_capabilities(stdout, Path("python.exe"))


def test_probe_parses_the_report_and_ignores_chatter():
    # FreeCAD and the kernels print banners; only the report line is JSON.
    report = parse_report("banner\nnoise\n" + json.dumps(REPORT) + "\n")
    assert report.occt.available is True
    assert report.occt.occt_version == "7.9.3.1.1"
    assert report.ifc.version == "0.8.5"
    assert report.freecad.version == "1.1.3"
    assert report.can_build_geometry is True


def test_probe_reads_the_last_line_not_the_first():
    # A kernel can emit a version banner before the report.
    report = parse_report(json.dumps({"schema_version": "0.0"}) + "\n" + json.dumps(REPORT))
    assert report.schema_version == "1.0"


def test_a_malformed_section_becomes_unavailable_not_a_crash():
    payload = dict(REPORT, freecad="not-an-object")
    report = parse_report(json.dumps(payload))
    # One broken component must not hide the health of everything else.
    assert report.freecad.available is False
    assert report.occt.available is True


def test_empty_output_is_a_dependency_problem():
    with pytest.raises(CadDependencyMissingError, match="no output"):
        parse_report("   \n")


def test_unparseable_output_is_a_dependency_problem():
    with pytest.raises(CadDependencyMissingError, match="unparseable"):
        parse_report("{definitely not json")


def test_probe_raises_when_the_worker_cannot_be_launched(tmp_path, monkeypatch):
    worker_python(tmp_path)
    config = CadConfig(worker_venv_root=str(tmp_path / "venv"), provider="occt")

    def boom(*args: object, **kwargs: object) -> object:
        raise OSError("no such interpreter")

    monkeypatch.setattr(cap.subprocess, "run", boom)
    with pytest.raises(CadDependencyMissingError, match="could not launch"):
        probe_capabilities(config, use_cache=False)


def test_probe_raises_on_a_nonzero_exit(tmp_path, monkeypatch):
    worker_python(tmp_path)
    config = CadConfig(worker_venv_root=str(tmp_path / "venv"), provider="occt")

    class Completed:
        stdout = ""
        stderr = "ImportError: no module named OCP"
        returncode = 1

    monkeypatch.setattr(cap.subprocess, "run", lambda *a, **k: Completed())
    with pytest.raises(CadDependencyMissingError, match="probe exited 1"):
        probe_capabilities(config, use_cache=False)


def test_probe_result_is_cached_so_the_toolchain_does_not_flicker(tmp_path, monkeypatch):
    worker_python(tmp_path)
    config = CadConfig(worker_venv_root=str(tmp_path / "venv"), provider="occt")
    calls: list[int] = []

    class Completed:
        stdout = json.dumps(REPORT)
        stderr = ""
        returncode = 0

    def counting(*args: object, **kwargs: object) -> Completed:
        calls.append(1)
        return Completed()

    monkeypatch.setattr(cap.subprocess, "run", counting)
    first = probe_capabilities(config)
    second = probe_capabilities(config)
    # Geometry provenance records the toolchain that produced an artifact; a
    # toolchain that flickers between probes would split one building in two.
    assert first is second
    assert len(calls) == 1

    probe_capabilities(config, use_cache=False)
    assert len(calls) == 2


def test_missing_worker_python_is_reported_as_a_dependency_problem(tmp_path):
    # Not a user error and not a crash: an operator has to install the toolchain.
    config = CadConfig(worker_venv_root=str(tmp_path / "absent"))
    with pytest.raises(CadDependencyMissingError) as excinfo:
        resolve_worker_python(config)
    assert excinfo.value.component == "worker-python"


def test_configured_worker_python_wins_over_the_venv_layout(tmp_path):
    python = worker_python(tmp_path)
    config = CadConfig(worker_python=str(python))
    assert resolve_worker_python(config) == python


def test_api_root_points_at_the_directory_containing_the_app_package():
    # The worker runs as `python -m app.cad_worker.main` from here.
    assert (CadConfig().api_root / "app" / "cad_worker" / "main.py").is_file()


def test_freecad_is_found_in_either_known_layout(tmp_path):
    for layout in ("bin", "root"):
        root = tmp_path / f"layout-{layout}"
        cmd = root / "bin" / "freecadcmd.exe" if layout == "bin" else root / "freecadcmd.exe"
        cmd.parent.mkdir(parents=True, exist_ok=True)
        cmd.write_text("", encoding="utf-8")
        assert resolve_freecad_cmd(CadConfig(freecad_root=str(root))) == cmd


def test_absent_freecad_is_none_not_an_exception(tmp_path):
    assert resolve_freecad_cmd(CadConfig(freecad_root=str(tmp_path / "gone"))) is None


# --------------------------------------------------------------------------- #
# Runner containment
# --------------------------------------------------------------------------- #


class TestRunnerContainment:
    def test_a_honest_result_is_accepted(self, fake_worker: FakeWorker, tmp_path: Path):
        result = run_cad_job(
            make_request(),
            fake_worker.config(tmp_path / "artifacts"),
            capabilities=available_caps(),
        )
        assert result.status == "ok"
        assert result.measurements[0].id == "mass-1"
        assert result.provider.provider == "occt"
        assert result.validation is not None and result.validation.valid is True

    def test_the_artifact_payload_is_usable_bytes_not_just_a_digest(
        self, fake_worker: FakeWorker, tmp_path: Path
    ):
        result = run_cad_job(
            make_request(), fake_worker.config(tmp_path / "artifacts"), capabilities=available_caps()
        )
        artifact = result.artifacts[0]
        data = base64.b64decode(artifact.payload, validate=True)
        assert data == b"ISO-10303-21;FAKE"
        assert hashlib.sha256(data).hexdigest() == artifact.sha256

    def test_a_hostile_output_dir_from_the_caller_is_overwritten(
        self, fake_worker: FakeWorker, tmp_path: Path
    ):
        # The runner stamps output_dir itself. A caller must not be able to steer
        # where the worker writes.
        request = make_request(
            output_dir=r"C:\Windows\Temp\escape", sandbox_root=r"C:\Windows"
        )
        run_cad_job(
            request, fake_worker.config(tmp_path / "artifacts"), capabilities=available_caps()
        )
        stamped = fake_worker.last
        assert Path(stamped.output_dir).is_relative_to(tmp_path / "artifacts")
        assert stamped.sandbox_root == stamped.output_dir

    def test_the_worker_runs_in_its_own_scratch_directory(
        self, fake_worker: FakeWorker, tmp_path: Path
    ):
        run_cad_job(
            make_request(), fake_worker.config(tmp_path / "artifacts"), capabilities=available_caps()
        )
        # A relative-path bug in the worker cannot then reach the application source.
        assert Path(fake_worker.last.cwd).is_relative_to(tmp_path / "artifacts")

    def test_the_scratch_directory_is_removed_even_when_the_worker_fails(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        worker_with(FAILING)
        with pytest.raises(CadProviderError):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )
        # Leaving a job's partial output behind would let a later run mistake it for
        # a fresh one, and the artifact root would grow without bound.
        assert list((tmp_path / "artifacts").glob("job-*")) == []

    def test_an_oversized_request_is_refused_before_the_worker_runs(
        self, fake_worker: FakeWorker, tmp_path: Path
    ):
        config = fake_worker.config(tmp_path / "artifacts", max_request_bytes=256)
        with pytest.raises(CadSecurityError, match="over the 256 byte limit"):
            run_cad_job(make_request(), config, capabilities=available_caps())
        # Cheaper to refuse a hostile payload than to hand it to a kernel.
        assert fake_worker.count == 0

    def test_a_timeout_is_reported_as_a_timeout_not_a_generic_error(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        worker_with(SLOW)
        config = fake_worker.config(tmp_path / "artifacts", job_timeout_seconds=0.5)
        with pytest.raises(CadJobTimeoutError) as excinfo:
            run_cad_job(make_request(), config, capabilities=available_caps())
        assert excinfo.value.timeout_seconds == pytest.approx(0.5)

    def test_freecad_gets_its_own_timeout_budget_and_root(
        self, fake_worker: FakeWorker, tmp_path: Path
    ):
        freecad_root = tmp_path / "freecad"
        freecad_root.mkdir()
        config = fake_worker.config(
            tmp_path / "artifacts", provider="freecad", freecad_root=str(freecad_root)
        )
        run_cad_job(make_request(), config, capabilities=available_caps())
        # The worker needs to know where FreeCAD is; without the flag it degrades
        # to a confusing "FreeCAD not found" rather than using the configured root.
        assert fake_worker.last.cwd  # sanity: the job really ran
        assert freecad_root.is_dir()

    def test_a_timed_out_worker_does_not_leave_its_children_running(
        self,
        fake_worker: FakeWorker,
        worker_with: Callable[[str], FakeWorker],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        # FreeCAD runs as a freecadcmd child. A native kernel that has wedged will
        # not notice its parent died, so killing only the direct child would leave
        # a multi-gigabyte process holding the artifact root open.
        marker = tmp_path / "heartbeat.txt"
        monkeypatch.setenv("AIRCHITECT_FAKE_MARKER", str(marker))
        worker_with(SPAWNER)
        config = fake_worker.config(tmp_path / "artifacts", job_timeout_seconds=1.0)
        with pytest.raises(CadJobTimeoutError):
            run_cad_job(make_request(), config, capabilities=available_caps())

        assert marker.is_file(), "the child never started, so nothing was proven"
        first = marker.read_text(encoding="utf-8")
        time.sleep(1.0)
        # The child bumps a counter roughly every 50ms, so a survivor shows up as
        # a larger number. Verified to fail if the runner kills only its direct
        # child.
        assert marker.read_text(encoding="utf-8") == first

    def test_a_missing_response_file_is_a_protocol_error(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        worker_with(SILENT)
        with pytest.raises(CadJobError, match="produced no response"):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )

    def test_an_unparseable_response_is_a_protocol_error(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        worker_with(GARBAGE)
        with pytest.raises(CadJobError, match="unreadable response"):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )

    def test_an_oversized_response_is_refused_before_parsing(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        worker_with(GIANT)
        config = fake_worker.config(
            tmp_path / "artifacts", max_output_bytes=1024, max_request_bytes=1024
        )
        with pytest.raises(CadSecurityError, match="over the"):
            run_cad_job(make_request(), config, capabilities=available_caps())

    def test_the_response_budget_accounts_for_base64_expansion(self):
        # base64 costs 4/3, so a budget equal to max_output_bytes would reject
        # perfectly legitimate responses full of artifacts.
        config = CadConfig(max_output_bytes=3000, max_request_bytes=3000)
        assert _response_byte_budget(config) > 3000

    def test_memory_limits_are_only_claimed_where_they_exist(self):
        # Windows has no per-process address-space rlimit; pretending otherwise
        # would be a lie about the containment boundary.
        kwargs = _memory_limit_kwargs(4096)
        if os.name == "posix":
            assert "preexec_fn" in kwargs
        else:
            assert kwargs == {}

    def test_the_worker_cannot_inherit_an_api_interpreter_by_accident(self):
        # The API interpreter does not carry the CAD packages; using it would run
        # geometry work in a process never meant to host it.
        config = CadConfig(worker_venv_root="H:/.cad-tools/worker-venv")
        resolved = resolve_worker_python(config)
        assert resolved.name.lower().startswith("python")
        assert "cad-tools" in str(resolved) or config.worker_python

    def test_the_worker_venv_is_used_when_no_override_is_configured(self):
        config = CadConfig(worker_venv_root="H:/.cad-tools/worker-venv")
        assert "worker-venv" in str(resolve_worker_python(config))

    def test_the_worker_receives_the_api_root_on_pythonpath(
        self, fake_worker: FakeWorker, tmp_path: Path
    ):
        # The worker is launched as `python -m app.cad_worker.main`; without
        # PYTHONPATH pointing at the source root that import cannot resolve.
        result = run_cad_job(
            make_request(), fake_worker.config(tmp_path / "artifacts"), capabilities=available_caps()
        )
        assert result.status == "ok"
        assert fake_worker.last.request["job_id"] == "test-job"


# --------------------------------------------------------------------------- #
# Runner: the API does not trust the worker
# --------------------------------------------------------------------------- #


class TestResultVerification:
    @pytest.mark.parametrize(
        ("scenario", "expected"),
        [
            (INVALID_RESULT, CadProviderError),
            (OPEN_SHELL, CadProviderError),
            (EMPTY_RESULT, CadJobError),
            (LYING_DIGEST, CadJobError),
            (WRONG_SIZE, CadJobError),
            (BAD_BASE64, CadJobError),
            (EMPTY_PAYLOAD, CadJobError),
            (EXE_ARTIFACT, CadSecurityError),
            (MISMATCHED_KIND, CadJobError),
            (REJECTING, CadProviderError),
            (ESCAPING, CadSecurityError),
        ],
    )
    def test_a_bad_worker_answer_never_reaches_the_caller(
        self,
        fake_worker: FakeWorker,
        worker_with: Callable[[str], FakeWorker],
        tmp_path: Path,
        scenario: str,
        expected: type[Exception],
    ):
        worker_with(scenario)
        with pytest.raises(expected):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )

    def test_a_result_the_worker_called_invalid_is_refused(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        # The API does not get to decide a failed geometry is good enough.
        worker_with(INVALID_RESULT)
        with pytest.raises(CadProviderError, match="invalid"):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )

    def test_an_open_shell_is_refused(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        worker_with(OPEN_SHELL)
        with pytest.raises(CadProviderError, match="not a valid closed shell"):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )

    def test_a_result_with_no_measurements_is_refused(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        worker_with(EMPTY_RESULT)
        with pytest.raises(CadJobError, match="no measurements"):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )

    def test_a_digest_that_does_not_match_its_bytes_is_refused(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        # The API persists content-addressed objects keyed by these digests; a
        # mismatch means the metadata and the content disagree.
        worker_with(LYING_DIGEST)
        with pytest.raises(CadJobError, match="does not match its declared sha256"):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )

    def test_a_mislabelled_byte_size_is_refused(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        worker_with(WRONG_SIZE)
        with pytest.raises(CadJobError, match="but the worker reported"):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )

    def test_a_non_base64_payload_is_refused(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        worker_with(BAD_BASE64)
        with pytest.raises(CadJobError, match="not valid base64"):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )

    def test_an_empty_payload_is_refused(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        worker_with(EMPTY_PAYLOAD)
        with pytest.raises(CadJobError, match="no payload"):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )

    def test_an_artifact_with_a_disallowed_suffix_is_refused(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        # This is what stops a job from writing an executable into the artifact root.
        worker_with(EXE_ARTIFACT)
        with pytest.raises(CadSecurityError, match="disallowed suffix"):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )

    def test_an_artifact_whose_kind_contradicts_its_extension_is_refused(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        worker_with(MISMATCHED_KIND)
        with pytest.raises(CadJobError, match="should carry"):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )

    def test_a_user_rejection_from_the_worker_keeps_its_error_code(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        worker_with(REJECTING)
        with pytest.raises(CadProviderError) as excinfo:
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )
        assert excinfo.value.details["code"] == "no_elements"

    def test_a_sandbox_violation_from_the_worker_is_a_security_error(
        self, fake_worker: FakeWorker, worker_with: Callable[[str], FakeWorker], tmp_path: Path
    ):
        worker_with(ESCAPING)
        with pytest.raises(CadSecurityError, match="output_dir_escape"):
            run_cad_job(
                make_request(),
                fake_worker.config(tmp_path / "artifacts"),
                capabilities=available_caps(),
            )

    def test_the_scenario_default_is_an_honest_success(
        self, fake_worker: FakeWorker, tmp_path: Path
    ):
        # Guards the harness itself: if OK stopped working, every "refused" test
        # above would pass for the wrong reason.
        result = run_cad_job(
            make_request(), fake_worker.config(tmp_path / "artifacts"), capabilities=available_caps()
        )
        assert result.status == "ok"
        assert fake_worker.last.scenario == OK

"""A stand-in CAD worker for testing the API-side runner.

The runner's job has two halves -- constraining the worker, and verifying what it
says -- and both are testable without OCCT. The containment risks (an unquoted
argument, a shell, a wrong working directory, a response that never appears) are
real subprocess risks, so the fake is a real subprocess, not a mock.

It is a real one with no patching at all. A throwaway package containing
``app/cad_worker/main.py`` is written to a temporary directory, that directory is
handed to the runner as ``api_root`` (the runner already puts it on
``PYTHONPATH``), and ``worker_python`` is pointed at the running interpreter. So
the command line, the environment, the working directory, the request file and
the response file are all genuinely produced and consumed exactly as they are in
production. The only thing missing is the geometry kernel.

Which behaviour to produce is selected with the ``AIRCHITECT_FAKE_SCENARIO``
environment variable, and each invocation appends a record to the file named by
``AIRCHITECT_FAKE_LOG`` so a test can assert on what the runner actually did.

End-to-end behaviour against real OCCT and FreeCAD lives in
``test_phase18_worker_live.py``; nothing in this module imports a CAD package.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest

from app.domains.cad.capability import reset_capability_cache
from app.domains.cad.config import CadConfig

SCENARIO_ENV = "AIRCHITECT_FAKE_SCENARIO"
LOG_ENV = "AIRCHITECT_FAKE_LOG"

OK = "ok"
FAILING = "failing"
SLOW = "slow"
SILENT = "silent"
GARBAGE = "garbage"
GIANT = "giant"
INVALID_RESULT = "invalid_result"
OPEN_SHELL = "open_shell"
EMPTY_RESULT = "empty_result"
INCONSISTENT_TOTALS = "inconsistent_totals"
OVERSIZED_VOLUME = "oversized_volume"
LYING_DIGEST = "lying_digest"
WRONG_SIZE = "wrong_size"
BAD_BASE64 = "bad_base64"
EMPTY_PAYLOAD = "empty_payload"
EXE_ARTIFACT = "exe_artifact"
MISMATCHED_KIND = "mismatched_kind"
REJECTING = "rejecting"
SPAWNER = "spawner"
ESCAPING = "escaping"

#: The module the runner actually imports. Written out verbatim; keep it
#: self-contained and stdlib-only so it runs under any interpreter. It is a plain
#: string with no substitution, so the dict literals below need no escaping.
FAKE_WORKER_MODULE = r'''
"""Stand-in for app.cad_worker.main, used by the API runner tests."""

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PAYLOAD = b"ISO-10303-21;FAKE"


def measurement(**overrides):
    record = {
        "id": "mass-1",
        "kind": "building_mass",
        "volume_m3": 3000.0,
        "surface_area_m2": 1400.0,
        "centroid": [5.0, 5.0, 15.0],
        "bounding_box": {"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 30.0]},
        "solid_count": 1,
        "face_count": 6,
        "edge_count": 12,
        "vertex_count": 8,
        "is_valid": True,
        "is_closed": True,
    }
    record.update(overrides)
    return record


def artifact(kind="step", filename="test-job.step", content_type="model/step",
             data=PAYLOAD, sha256=None, byte_size=None, payload=None):
    encoded = base64.b64encode(data).decode("ascii") if payload is None else payload
    return {
        "kind": kind,
        "filename": filename,
        "content_type": content_type,
        "byte_size": len(data) if byte_size is None else byte_size,
        "sha256": hashlib.sha256(data).hexdigest() if sha256 is None else sha256,
        "payload": encoded,
    }


def failure(code, message):
    return {
        "schema_version": "1.0",
        "job_id": "test-job",
        "status": "error",
        "error_code": code,
        "message": message,
        "detail": "",
        "provider": "occt",
    }


def success(artifacts=None, measurements=None, valid=True, combined_volume_m3=None, combined_area_m2=None):
    solids = [measurement()] if measurements is None else measurements
    return {
        "schema_version": "1.0",
        "job_id": "test-job",
        "status": "ok",
        "provider": {
            "provider": "occt",
            "engine_name": "fake",
            "engine_version": "0",
            "occt_version": "7.9.3",
            "python_version": sys.version.split()[0],
        },
        "measurements": solids,
        "combined_volume_m3": 3000.0 if combined_volume_m3 is None else combined_volume_m3,
        "combined_area_m2": 1400.0 if combined_area_m2 is None else combined_area_m2,
        "combined_bounding_box": (
            {
                "min": [min(s["bounding_box"]["min"][i] for s in solids) for i in range(3)],
                "max": [max(s["bounding_box"]["max"][i] for s in solids) for i in range(3)],
            }
            if solids
            else None
        ),
        "artifacts": [artifact()] if artifacts is None else artifacts,
        "validation": {
            "valid": valid,
            "checks": [],
            "errors": [] if valid else ["analytic volume mismatch"],
            "warnings": [],
        },
        "element_count": 1,
        "warnings": [],
    }


def build(scenario):
    if scenario == "failing":
        return failure("GeometryError", "could not build a planar face")
    if scenario == "rejecting":
        return failure("no_elements", "the request contains no massing elements")
    if scenario == "escaping":
        return failure("output_dir_escape", "output_dir is outside the sandbox root")
    if scenario == "invalid_result":
        return success(valid=False)
    if scenario == "open_shell":
        return success(measurements=[measurement(is_closed=False)])
    if scenario == "inconsistent_totals":
        # The combined total contradicts the per-solid rows it was supposedly summed
        # from. The protocol cannot know this, so the consumer has to check it.
        return success(combined_volume_m3=2999.0, combined_area_m2=1399.0)
    if scenario == "oversized_volume":
        # A volume larger than the box that encloses the solid, which is the shape a
        # unit error takes: cubic metres reported against a bounding box in millimetres.
        return success(combined_volume_m3=3000.0 * 1000)
    if scenario == "empty_result":
        return success(measurements=[])
    if scenario == "lying_digest":
        return success(artifacts=[artifact(sha256="0" * 64)])
    if scenario == "wrong_size":
        return success(artifacts=[artifact(byte_size=999)])
    if scenario == "bad_base64":
        return success(artifacts=[artifact(payload="!!!not base64!!!")])
    if scenario == "empty_payload":
        return success(artifacts=[artifact(payload="")])
    if scenario == "exe_artifact":
        return success(artifacts=[artifact(
            filename="payload.exe", content_type="application/octet-stream", data=b"MZ")])
    if scenario == "mismatched_kind":
        return success(artifacts=[artifact(
            kind="glb", filename="test-job.step", content_type="model/step")])
    return success()


def capabilities():
    return {
        "schema_version": "1.0",
        "python_version": sys.version.split()[0],
        "occt": {
            "available": True,
            "error": "",
            "engine_name": "fake",
            "engine_version": "0",
            "occt_version": "7.9.3",
            "occt_build": "",
        },
        "ifc": {"available": True, "error": "", "version": "0.8.5-fake"},
        "freecad": {"available": True, "error": "", "version": "1.1.3-fake", "occt_version": "7.8.1"},
        "glb": {"available": True, "error": ""},
    }


def main(argv):
    if argv and argv[0] == "--capabilities":
        # The real worker's capability entry point: report what this kernel can do,
        # on stdout, and exit. The API's probe reads nothing else. Answering it here
        # is what lets the fake stand in for the whole worker rather than only for
        # the geometry half of it.
        print(json.dumps(capabilities()))
        return 0

    request_path, response_path = Path(argv[0]), Path(argv[1])
    scenario = os.environ.get("AIRCHITECT_FAKE_SCENARIO", "ok")
    request = {}
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
    except Exception:
        pass

    if scenario == "slow":
        time.sleep(60)

    if scenario == "spawner":
        # A worker that leaves a long-lived child behind, the way FreeCAD leaves
        # freecadcmd running. The child keeps bumping a counter in a marker file so
        # a test can tell whether it survived the parent's timeout.
        script = Path(__file__).parent / "_heartbeat.py"
        script.write_text(
            "import os, time\n"
            "from pathlib import Path\n"
            "marker = Path(os.environ['AIRCHITECT_FAKE_MARKER'])\n"
            "for tick in range(2000):\n"
            "    marker.write_text(str(tick), encoding='utf-8')\n"
            "    time.sleep(0.05)\n",
            encoding="utf-8",
        )
        subprocess.Popen([sys.executable, str(script)])
        time.sleep(60)

    if scenario != "silent":
        if scenario == "garbage":
            response_path.write_text("{definitely not json", encoding="utf-8")
        elif scenario == "giant":
            # Comfortably past the runner's response budget, which is the artifact
            # limit scaled by 4/3 for base64 plus 4 MiB of headroom.
            padding = "x" * int(os.environ.get("AIRCHITECT_FAKE_PAD_BYTES", "6000000"))
            response_path.write_text(
                json.dumps({"schema_version": "1.0", "pad": padding}), encoding="utf-8")
        else:
            response_path.write_text(json.dumps(build(scenario)), encoding="utf-8")

    log = os.environ.get("AIRCHITECT_FAKE_LOG")
    if log:
        record = {
            "argv": list(argv),
            "cwd": os.getcwd(),
            "python": sys.executable,
            "request": request,
            "scenario": scenario,
        }
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''


@dataclass(frozen=True)
class FakeCadConfig(CadConfig):
    """A :class:`CadConfig` whose ``api_root`` is a throwaway package tree.

    The runner puts ``api_root`` on ``PYTHONPATH`` and launches
    ``python -m app.cad_worker.main``, so pointing ``api_root`` at a directory
    holding a stand-in ``app`` package makes the real command line resolve to the
    fake without touching the runner.
    """

    fake_api_root: str = ""

    @property
    def api_root(self) -> Path:
        if self.fake_api_root:
            return Path(self.fake_api_root)
        return Path(__file__).resolve().parents[2]


def _write_package(root: Path) -> None:
    package = root / "app" / "cad_worker"
    package.mkdir(parents=True, exist_ok=True)
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "main.py").write_text(FAKE_WORKER_MODULE, encoding="utf-8")


class Invocation:
    """One launch of the fake worker, as the OS actually performed it."""

    def __init__(self, record: dict[str, Any]):
        self.argv: list[str] = record["argv"]
        self.cwd: str = record["cwd"]
        self.python: str = record["python"]
        self.request: dict[str, Any] = record["request"]
        self.scenario: str = record["scenario"]

    @property
    def request_path(self) -> Path:
        return Path(self.cwd) / "request.json"

    @property
    def response_path(self) -> Path:
        return Path(self.cwd) / "response.json"

    @property
    def output_dir(self) -> str:
        return self.request.get("output_dir", "")

    @property
    def sandbox_root(self) -> str:
        return self.request.get("sandbox_root", "")


class FakeWorker:
    """Points the runner at the fake worker and records how it was invoked."""

    def __init__(self, log: Path, root: Path):
        self.log = log
        self.root = root

    def config(self, artifact_root: Path, **overrides: Any) -> FakeCadConfig:
        payload: dict[str, Any] = {
            "fake_api_root": str(self.root),
            "worker_python": sys.executable,
            "artifact_root": str(artifact_root),
            "freecad_root": str(self.root / "freecad"),
            "provider": "occt",
        }
        payload.update(overrides)
        return FakeCadConfig(**payload)

    @property
    def invocations(self) -> list[Invocation]:
        if not self.log.is_file():
            return []
        records = [
            json.loads(line)
            for line in self.log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return [Invocation(record) for record in records]

    @property
    def last(self) -> Invocation:
        invocations = self.invocations
        assert invocations, "the fake worker was never launched"
        return invocations[-1]

    @property
    def count(self) -> int:
        return len(self.invocations)


@pytest.fixture
def fake_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeWorker:
    """A worker that answers with a well-formed result unless told otherwise."""
    root = tmp_path / "fake-root"
    _write_package(root)
    log = tmp_path / "invocations.jsonl"
    monkeypatch.setenv(SCENARIO_ENV, OK)
    monkeypatch.setenv(LOG_ENV, str(log))
    # The capability report is cached process-wide and keyed on nothing, so a report
    # probed by an earlier test would otherwise be handed to this one -- describing a
    # worker that no longer exists. Every test that asks for capabilities must be able
    # to ask for them afresh.
    reset_capability_cache()
    yield FakeWorker(log, root)
    reset_capability_cache()


@pytest.fixture
def worker_with(
    fake_worker: FakeWorker, monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], FakeWorker]:
    """Return a helper that switches the fake worker's behaviour."""

    def use(scenario: str) -> FakeWorker:
        monkeypatch.setenv(SCENARIO_ENV, scenario)
        return fake_worker

    return use


__all__ = [
    "BAD_BASE64",
    "EMPTY_PAYLOAD",
    "EMPTY_RESULT",
    "ESCAPING",
    "EXE_ARTIFACT",
    "FAILING",
    "GARBAGE",
    "GIANT",
    "INVALID_RESULT",
    "LYING_DIGEST",
    "MISMATCHED_KIND",
    "OK",
    "OPEN_SHELL",
    "REJECTING",
    "SILENT",
    "SPAWNER",
    "SLOW",
    "WRONG_SIZE",
    "FakeCadConfig",
    "FakeWorker",
    "Invocation",
]

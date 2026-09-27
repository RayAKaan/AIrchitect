"""Discovery of the installed CAD toolchain.

The API must never *assume* a CAD library is present. ``cadquery-ocp`` and
IfcOpenShell live in a separate virtualenv precisely so the API image does not
carry them, which means every deployment has to be asked what it actually has
before it can be trusted to produce geometry. This module is that question, asked
exactly once and cached.

Two things are deliberately kept apart:

* :class:`CadConfig` describes the *policy* -- which provider is allowed, how
  long a job may run, where artifacts go.
* This module reports *reality* -- which interpreter exists, which OCCT it links
  against, whether FreeCAD can be launched.

Conflating them is how deployments become undebuggable: a config that says
``provider=freecad`` on a machine with no FreeCAD must degrade to OCCT and say
so, not fail at import time and not silently produce nothing.

Capability probing is cached because it is comparatively expensive (it launches
FreeCAD, which takes seconds) and because a *stable* answer is more useful than a
freshly measured one: geometry provenance records the toolchain that produced an
artifact, and a toolchain that flickers between probes would make the same
building look like two different buildings.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domains.cad.config import CadConfig
from app.domains.cad.errors import CadDependencyMissingError

#: Environment variable pointing the worker at the API source tree.
#:
#: The worker is executed as ``python -m app.cad_worker.main`` from the API
#: checkout, so the API root has to be importable. It is set explicitly rather
#: than inherited because the worker's virtualenv has its own site-packages and
#: must not resolve ``app`` from anywhere else.
WORKER_PYTHONPATH_ENV = "AIRCHITECT_CAD_PYTHONPATH"

#: How long a cached capability report stays fresh.
CAPABILITY_TTL_SECONDS = 300.0

#: A capability probe is a health check, not a geometry job, so it gets a short
#: budget of its own. FreeCAD's import alone can take several seconds.
CAPABILITY_TIMEOUT_SECONDS = 120.0

ProviderName = Literal["occt", "freecad"]


class KernelCapabilities(BaseModel):
    """What one CAD kernel can do in this deployment."""

    available: bool = False
    error: str = ""


class OcctCapabilities(KernelCapabilities):
    """OCCT as reachable through the worker's own interpreter."""

    engine_name: str = ""
    engine_version: str = ""
    occt_version: str | None = None
    occt_build: str | None = None


class IfcCapabilities(KernelCapabilities):
    """IfcOpenShell, which drives IFC export independently of the solid kernel."""

    version: str | None = None


class FreecadCapabilities(KernelCapabilities):
    """FreeCAD, which is a second, independent implementation of the same geometry."""

    version: str | None = None
    occt_version: str | None = None


class WorkerCapabilities(BaseModel):
    """A snapshot of what the configured worker can actually do."""

    schema_version: str = "1.0"
    python_version: str = ""
    worker_python: str = ""
    occt: OcctCapabilities = Field(default_factory=OcctCapabilities)
    ifc: IfcCapabilities = Field(default_factory=IfcCapabilities)
    freecad: FreecadCapabilities = Field(default_factory=FreecadCapabilities)
    glb: KernelCapabilities = Field(default_factory=KernelCapabilities)
    probed_at: float = 0.0

    @property
    def can_build_geometry(self) -> bool:
        """Return True when at least one solid kernel is usable.

        IFC and GLB support are not enough on their own: they describe artifacts
        *of* geometry, so without a kernel there is nothing to describe.
        """
        return self.occt.available or self.freecad.available

    def select_provider(self, requested: str) -> str:
        """Resolve a requested provider to one that actually works here.

        ``auto`` prefers FreeCAD because it is the richer implementation, but
        falls back to OCCT rather than failing: a building that is one IFC schema
        revision behind is a far better outcome than no building.

        An *explicit* provider is honoured or refused, never silently swapped.
        Silently ignoring an operator's ``--provider freecad`` would make it
        impossible to tell a FreeCAD regression from an OCCT one.
        """
        if requested == "auto":
            if self.freecad.available:
                return "freecad"
            if self.occt.available:
                return "occt"
            raise CadDependencyMissingError(
                "cad-kernel",
                self.occt.error or self.freecad.error or "no kernel reported available",
            )
        if requested == "freecad":
            if not self.freecad.available:
                raise CadDependencyMissingError("freecad", self.freecad.error or "not available")
            return "freecad"
        if requested == "occt":
            if not self.occt.available:
                raise CadDependencyMissingError("occt", self.occt.error or "not available")
            return "occt"
        raise ValueError(f"unknown provider {requested!r}")

    def provenance(self) -> dict[str, str]:
        """Return the toolchain identity to record alongside generated geometry.

        Only real, reported values are included. A missing FreeCAD is recorded as
        absent rather than as an empty string, so the provenance record cannot be
        misread as "FreeCAD 0.0 produced this".
        """
        record = {
            "worker_python_version": self.python_version,
            "occt_version": self.occt.occt_version or "",
            "occt_build": self.occt.occt_build or "",
            "ifcopenshell_version": self.ifc.version or "",
        }
        if self.freecad.available:
            record["freecad_version"] = self.freecad.version or ""
            record["freecad_occt_version"] = self.freecad.occt_version or ""
        return record


@dataclass
class CapabilityCache:
    """Process-local cache of the most recent capability probe."""

    report: WorkerCapabilities | None = None
    fetched_at: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def get_fresh(self, ttl: float = CAPABILITY_TTL_SECONDS) -> WorkerCapabilities | None:
        """Return the cached report when it is still within *ttl*."""
        if self.report is None:
            return None
        if (time.monotonic() - self.fetched_at) > ttl:
            return None
        return self.report

    def store(self, report: WorkerCapabilities) -> None:
        self.report = report
        self.fetched_at = time.monotonic()


_CACHE = CapabilityCache()


def resolve_worker_python(config: CadConfig) -> Path:
    """Return the interpreter that will run the CAD worker.

    An explicitly configured ``worker_python`` wins. Otherwise the conventional
    layout inside ``worker_venv_root`` is used. The API's *own* interpreter is
    never returned: it does not have the CAD packages, and using it would defeat
    the isolation the whole design depends on.
    """
    if config.worker_python:
        candidate = Path(config.worker_python)
    else:
        candidate = config.worker_venv_root_path() / "Scripts" / "python.exe"
    if not candidate.is_file():
        raise CadDependencyMissingError("worker-python", f"not found at {candidate}")
    return candidate


def resolve_freecad_cmd(config: CadConfig) -> Path | None:
    """Return the ``freecadcmd.exe`` path if the configured root contains one.

    Both portable-build layouts are checked: the 7-Zip portable tree keeps the
    console executable in ``bin/``, while the installer puts it at the root.
    """
    root = Path(config.freecad_root)
    for relative in (Path("bin") / "freecadcmd.exe", Path("freecadcmd.exe")):
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return None


def probe_capabilities(
    config: CadConfig,
    *,
    timeout: float = CAPABILITY_TIMEOUT_SECONDS,
    use_cache: bool = True,
) -> WorkerCapabilities:
    """Ask the worker what it can do, and return a validated report.

    Never raises for a missing optional dependency: a report with
    ``available=False`` and an explanatory ``error`` is far more useful to a
    health endpoint than an exception, and it lets ``auto`` fall through to a
    kernel that does work.

    Raises :class:`CadDependencyMissingError` only when the worker itself cannot
    be launched, because at that point there is nothing left to degrade to.
    """
    if use_cache:
        cached = _CACHE.get_fresh()
        if cached is not None:
            return cached

    worker_python = resolve_worker_python(config)
    argv = [str(worker_python), "-m", "app.cad_worker.main", "--capabilities"]
    if config.freecad_root:
        argv += ["--freecad-root", config.freecad_root]

    env = _worker_env()
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(config.api_root),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CadDependencyMissingError("worker-python", f"capability probe timed out: {exc}") from exc
    except OSError as exc:
        raise CadDependencyMissingError("worker-python", f"could not launch: {exc}") from exc

    if completed.returncode != 0:
        raise CadDependencyMissingError(
            "worker-python",
            f"probe exited {completed.returncode}: {(completed.stderr or '').strip()[:400]}",
        )

    report = _parse_capabilities(completed.stdout, worker_python)
    if use_cache:
        _CACHE.store(report)
    return report


def _parse_capabilities(stdout: str, worker_python: Path) -> WorkerCapabilities:
    """Parse the worker's JSON capability report.

    The report is printed as the last line of stdout so that FreeCAD's banner and
    any import-time chatter do not have to be stripped precisely. Parsing is
    defensive: a partially broken report must still produce a usable object, since
    the whole point of the report is to describe a broken environment.
    """
    line = next(
        (candidate.strip() for candidate in reversed((stdout or "").splitlines()) if candidate.strip()),
        "",
    )
    if not line:
        raise CadDependencyMissingError("worker-python", "capability probe produced no output")
    try:
        payload: dict[str, Any] = json.loads(line)
    except json.JSONDecodeError as exc:
        raise CadDependencyMissingError("worker-python", f"unparseable capability report: {exc}") from exc

    return WorkerCapabilities(
        schema_version=str(payload.get("schema_version", "1.0")),
        python_version=str(payload.get("python_version", "")),
        worker_python=str(worker_python),
        occt=OcctCapabilities(**_as_dict(payload.get("occt"))),
        ifc=IfcCapabilities(**_as_dict(payload.get("ifc"))),
        freecad=FreecadCapabilities(**_as_dict(payload.get("freecad"))),
        glb=KernelCapabilities(**_as_dict(payload.get("glb"))),
        probed_at=time.time(),
    )


def _as_dict(value: Any) -> dict[str, Any]:
    """Return *value* when it is a mapping, otherwise an empty mapping.

    A missing or malformed section becomes an "unavailable" section rather than
    a parse failure, so one broken component does not hide the health of the rest.
    """
    return dict(value) if isinstance(value, dict) else {}


def reset_capability_cache() -> None:
    """Drop the cached report. Used by tests and by the reload endpoint."""
    with _CACHE.lock:
        _CACHE.report = None
        _CACHE.fetched_at = 0.0


def _worker_env() -> dict[str, str]:
    """Return the environment the worker subprocess is launched with."""
    env = dict(os.environ)
    root = str(_api_root())
    env[WORKER_PYTHONPATH_ENV] = root
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (root, env.get("PYTHONPATH", "")) if part
    )
    return env


def _api_root() -> Path:
    """Return the API source root that contains the ``app`` package."""
    return Path(__file__).resolve().parents[3]


__all__ = [
    "CAPABILITY_TIMEOUT_SECONDS",
    "CAPABILITY_TTL_SECONDS",
    "WORKER_PYTHONPATH_ENV",
    "FreecadCapabilities",
    "IfcCapabilities",
    "KernelCapabilities",
    "OcctCapabilities",
    "ProviderName",
    "WorkerCapabilities",
    "probe_capabilities",
    "reset_capability_cache",
    "resolve_freecad_cmd",
    "resolve_worker_python",
]

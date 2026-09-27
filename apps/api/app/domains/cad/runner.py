"""Bounded execution of the CAD worker.

This is the only place in the API that starts a CAD process, and it is written as
a containment boundary rather than a convenience wrapper. A worker builds geometry
from user-influenced input, so a malformed or hostile design must not be able to
consume the API's memory, hang a request thread, or write outside its scratch
directory. The specific controls are:

* **Wall-clock timeout.** Enforced by killing the whole process tree. A CAD kernel
  that wedges is the single most likely failure mode, and it must not take the
  request with it.
* **Memory limit.** Applied through the OS, not by hoping the worker behaves.
* **Sandboxed output directory.** Created by this module, inside the configured
  artifact root, and deleted afterwards. The worker validates it again on its
  side; validating on only one side would mean trusting the process that is being
  constrained.
* **Bounded request and response sizes.** Checked before the request is written
  and before the response is parsed, so neither side can exhaust memory by
  declaring an enormous payload.
* **No shell.** ``shell=False`` always. A job name or project name is
  attacker-influenced text and must never reach a command line.

The runner does *not* trust the worker's own verdict. It re-derives every
artifact's SHA-256 from the bytes the worker returned, and refuses the whole job
if a digest disagrees -- because a mismatched digest is the signature of a
corrupted or substituted artifact, and the entire persistence layer keys on
content hashes.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.domains.cad.capability import (
    WorkerCapabilities,
    probe_capabilities,
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
from app.domains.cad.protocol import (
    ALLOWED_ARTIFACT_SUFFIXES,
    ARTIFACT_EXTENSIONS,
    CadJobFailure,
    CadJobRequest,
    CadJobResult,
)

#: Extra seconds allowed past the job's own deadline before the kill escalates.
#:
#: The worker enforces its own budget so it can write a structured timeout
#: response; this grace period lets that happen before the process is killed.
KILL_GRACE_SECONDS = 5.0

#: Return codes the worker uses to signal a class of failure.
#:
#: 0 success, 2 a request the worker refused (a user problem), 1 anything else
#: (a worker or toolchain problem). Mapping them keeps a bad request reported as
#: a 422 rather than a 500.
WORKER_EXIT_OK = 0
WORKER_EXIT_REQUEST_ERROR = 2


def run_cad_job(
    request: CadJobRequest,
    config: CadConfig | None = None,
    *,
    capabilities: WorkerCapabilities | None = None,
    provider: str | None = None,
) -> CadJobResult:
    """Execute *request* in a bounded worker and return the validated result.

    The call blocks for the duration of the job. Callers that must not block an
    event loop should use a thread pool or a task queue; the timeout here bounds
    the worst case, not the responsiveness.

    Raises:
        CadDependencyMissingError: the worker or kernel is not installed.
        CadJobTimeoutError: the job exceeded its wall-clock budget.
        CadSecurityError: the request tried to write outside the sandbox or
            exceeded a size limit.
        CadProviderError: the worker ran and reported a failure.
        CadJobError: the worker returned something that is not a valid result.
    """
    cfg = config or CadConfig()
    caps = capabilities if capabilities is not None else probe_capabilities(cfg)
    chosen = provider or cfg.provider
    resolved = caps.select_provider(chosen)

    with _sandboxed_output(cfg) as output_dir:
        request_path = _prepare_request(request, cfg, output_dir)
        response_path = output_dir / "response.json"
        argv = _build_argv(cfg, request_path, response_path, resolved)
        completed = _execute(argv, cfg, resolved, output_dir)
        response = _read_response(completed, response_path, cfg, resolved)
        return _parse_result(response, resolved)


def _build_argv(config: CadConfig, request_path: Path, response_path: Path, provider: str) -> list[str]:
    """Assemble the worker command line.

    Fixed argv, no shell, and no user-controlled text in the executable position.
    """
    argv = [
        str(resolve_worker_python(config)),
        "-m",
        "app.cad_worker.main",
        str(request_path),
        str(response_path),
        "--provider",
        provider,
    ]
    if provider == "freecad":
        argv += ["--freecad-root", config.freecad_root]
    return argv


def _prepare_request(
    request: CadJobRequest, config: CadConfig, output_dir: Path
) -> Path:
    """Validate, stamp, and write the request JSON.

    The output directory is stamped here rather than by the caller, so a caller
    cannot influence where the worker writes by passing its own ``output_dir``.
    """
    stamped = request.model_copy(
        update={"output_dir": str(output_dir), "sandbox_root": str(output_dir)}
    )
    document = json.dumps(stamped.model_dump(mode="json"), separators=(",", ":"))
    encoded = document.encode("utf-8")
    if len(encoded) > config.max_request_bytes:
        raise CadSecurityError(
            f"request is {len(encoded)} bytes, over the {config.max_request_bytes} byte limit"
        )
    path = output_dir / "request.json"
    path.write_bytes(encoded)
    return path


@contextmanager
def _sandboxed_output(config: CadConfig) -> Iterator[Path]:
    """Yield a fresh scratch directory inside the configured artifact root.

    The directory is removed on exit, including on failure. Leaving geometry
    behind after a crashed job would let a later run mistake one job's partial
    output for another's, and the artifact root would grow without bound.
    """
    root = config.artifact_root_path()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CadDependencyMissingError("artifact-root", f"cannot create {root}: {exc}") from exc

    try:
        scratch = Path(tempfile.mkdtemp(prefix="job-", dir=str(root)))
    except OSError as exc:
        raise CadSecurityError(f"cannot create a scratch directory under {root}: {exc}") from exc

    try:
        yield scratch
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _execute(
    argv: Sequence[str], config: CadConfig, provider: str, output_dir: Path
) -> subprocess.CompletedProcess[str]:
    """Run the worker under a wall-clock and memory limit."""
    timeout = (
        config.freecad_timeout_seconds if provider == "freecad" else config.job_timeout_seconds
    )
    env = dict(os.environ)
    api_root = str(config.api_root)
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (api_root, env.get("PYTHONPATH", "")) if part
    )
    # The worker writes only inside output_dir, so the working directory is the
    # scratch directory: a relative-path bug in the worker cannot then reach the
    # application source.
    try:
        process = subprocess.Popen(  # noqa: S603 - fixed argv, shell=False
            list(argv),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=str(output_dir),
            **_process_group_kwargs(),
            **_memory_limit_kwargs(config.worker_memory_limit_mb),
        )
    except OSError as exc:
        raise CadDependencyMissingError(f"{provider}-worker", f"could not launch: {exc}") from exc

    try:
        stdout, stderr = process.communicate(timeout=timeout + KILL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        # The worker is not the only process at risk: FreeCAD runs as a
        # freecadcmd child, and a native kernel that has wedged will not notice
        # that its parent died. Killing only the direct child would leave a
        # multi-gigabyte process holding the artifact root open, so the whole
        # group goes.
        _kill_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:  # pragma: no cover - kill already failed
            stdout, stderr = "", f"worker did not exit after SIGKILL; pid {process.pid}"
        raise CadJobTimeoutError(provider, timeout) from None

    return subprocess.CompletedProcess(list(argv), process.returncode, stdout, stderr)


def _process_group_kwargs() -> dict[str, Any]:
    """Return the keyword arguments that make the worker killable as a group.

    ``subprocess.run`` kills only the process it started. The worker launches
    ``freecadcmd`` as a child, so a timeout has to be able to reach the whole
    tree. On POSIX a new session gives the worker its own process group; on
    Windows a new process group is the closest equivalent and is what
    ``taskkill /T`` walks.
    """
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    """Terminate *process* and everything it started.

    Best effort by design: a process that has already exited, or a platform
    without the tool needed to walk the tree, must not turn a reported timeout
    into an unrelated crash. The caller raises :class:`CadJobTimeoutError`
    either way.
    """
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            # taskkill is the only tree-aware kill available without ctypes.
            subprocess.run(  # noqa: S603 - fixed argv, shell=False
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
                timeout=30,
            )
        else:
            _kill_posix_group(process.pid)
    except (OSError, ValueError, subprocess.SubprocessError):
        # The group may already be gone, or getpgid may fail if the child was
        # reaped concurrently. Fall back to the direct child.
        with contextlib.suppress(OSError):
            process.kill()


def _kill_posix_group(pid: int) -> None:
    """Send SIGKILL to the process group led by *pid*.

    ``killpg``/``getpgid``/``SIGKILL`` are POSIX-only, and mypy resolves ``os`` and
    ``signal`` against Windows stubs that lack them, so the call is isolated here
    and bound untyped. The only caller is guarded by an ``os.name`` check.
    """
    import os as _os
    import signal as _signal

    _os.killpg(_os.getpgid(pid), _signal.SIGKILL)  # type: ignore[attr-defined]


def _memory_limit_kwargs(limit_mb: int) -> dict[str, Any]:
    """Return subprocess keyword arguments that cap the worker's memory.

    On POSIX this is ``RLIMIT_AS`` plus ``RLIMIT_CPU`` in a ``preexec_fn``.
    Windows has no per-process address-space rlimit; the container image is the
    boundary there, and the timeout still bounds a runaway process. Returning an
    empty dict on Windows is honest about that rather than pretending a limit is
    in force.
    """
    if os.name != "posix":
        return {}
    byte_limit = limit_mb * 1024 * 1024
    cpu_limit = limit_mb

    def _apply() -> None:  # pragma: no cover - runs in the child process
        apply_posix_limits(byte_limit, cpu_limit)

    return {"preexec_fn": _apply}


def apply_posix_limits(address_space_bytes: int, cpu_seconds: int) -> None:
    """Apply rlimits in the forked child.

    ``resource`` is POSIX-only and mypy resolves it against a Windows stub that
    lacks these symbols, so the module is bound untyped here. The call is guarded
    by an ``os.name`` check at every entry point.
    """
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (address_space_bytes, address_space_bytes))  # type: ignore[attr-defined]
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))  # type: ignore[attr-defined]


def _read_response(
    completed: subprocess.CompletedProcess[str],
    response_path: Path,
    config: CadConfig,
    provider: str,
) -> dict[str, Any]:
    """Locate and size-check the response document."""
    if not response_path.is_file():
        raise CadJobError(
            f"{provider} worker produced no response (exit {completed.returncode}): "
            f"{(completed.stderr or '').strip()[:500]}"
        )
    size = response_path.stat().st_size
    budget = _response_byte_budget(config)
    if size > budget:
        raise CadSecurityError(f"response is {size} bytes, over the {budget} byte limit")
    try:
        document = json.loads(response_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CadJobError(f"{provider} worker wrote an unreadable response: {exc}") from exc
    if not isinstance(document, dict):
        raise CadJobError(f"{provider} worker response was {type(document).__name__}, not an object")
    return document


def _response_byte_budget(config: CadConfig) -> int:
    """Return the maximum acceptable response size.

    Artifacts are base64-encoded in the response, so the budget is the artifact
    limit scaled by 4/3 plus headroom for the measurement and validation records.
    """
    return int(config.max_output_bytes * 4 / 3) + 4_194_304


def _parse_result(response: dict[str, Any], provider: str) -> CadJobResult:
    """Turn a worker response into a validated :class:`CadJobResult`.

    Error responses become typed exceptions; success responses are re-validated
    and their artifact digests independently recomputed. A worker that reports a
    hash which does not match the bytes it sent is treated as a protocol failure,
    because the API would otherwise persist an artifact under a hash that
    identifies different content.
    """
    status = response.get("status")
    if status == "error":
        failure = _parse_failure(response)
        if failure.error_code in {
            "output_dir_escape",
            "missing_output_dir",
            "missing_sandbox",
            "disallowed_artifact_kind",
            "oversized_artifact",
        }:
            raise CadSecurityError(f"{failure.error_code}: {failure.message}")
        if failure.error_code in {
            "no_elements",
            "bad_element",
            "bad_element_id",
            "duplicate_element_id",
            "bad_height",
            "bad_footprint",
            "too_many_elements",
        }:
            raise CadProviderError(provider, failure.message, details={"code": failure.error_code})
        raise CadProviderError(
            provider,
            failure.message,
            details={"code": failure.error_code, "detail": failure.detail},
        )

    if status != "ok":
        raise CadJobError(f"worker returned status {status!r}, expected 'ok' or 'error'")

    try:
        result = CadJobResult.model_validate(response)
    except Exception as exc:
        raise CadJobError(f"worker response did not match the protocol: {exc}") from exc

    _verify_artifact_digests(result)
    _verify_worker_validation(result)
    return result


def _parse_failure(response: dict[str, Any]) -> CadJobFailure:
    """Parse an error response, tolerating a partially malformed one."""
    try:
        return CadJobFailure.model_validate(response)
    except Exception as exc:
        raise CadJobError(f"worker error response did not match the protocol: {exc}") from exc


def _verify_artifact_digests(result: CadJobResult) -> None:
    """Recompute every artifact digest from the payload the worker sent.

    This is the one trust boundary the API cannot delegate: the worker computes
    the digests, and the API persists content-addressed objects keyed by them. A
    mismatch means the bytes and the metadata disagree, so the job is rejected
    rather than stored.
    """
    for artifact in result.artifacts:
        suffix = Path(artifact.filename).suffix.lower()
        expected_suffix = ARTIFACT_EXTENSIONS[artifact.kind].lower()
        if suffix not in ALLOWED_ARTIFACT_SUFFIXES:
            raise CadSecurityError(
                f"worker returned artifact {artifact.filename!r} with disallowed suffix {suffix!r}"
            )
        if suffix != expected_suffix:
            raise CadJobError(
                f"artifact kind {artifact.kind!r} should carry {expected_suffix} "
                f"but the worker sent {suffix!r}"
            )
        if not artifact.payload:
            raise CadJobError(f"artifact {artifact.filename!r} arrived with no payload")
        try:
            data = base64.b64decode(artifact.payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise CadJobError(f"artifact {artifact.filename!r} is not valid base64: {exc}") from exc
        if len(data) != artifact.byte_size:
            raise CadJobError(
                f"artifact {artifact.filename!r} is {len(data)} bytes, "
                f"but the worker reported {artifact.byte_size}"
            )
        if hashlib.sha256(data).hexdigest() != artifact.sha256:
            raise CadJobError(
                f"artifact {artifact.filename!r} does not match its declared sha256; "
                "refusing to persist content under a hash that identifies something else"
            )


def _verify_worker_validation(result: CadJobResult) -> None:
    """Refuse a result the worker itself reported as invalid.

    The API does not get to decide that a failed geometry is good enough. If the
    kernel's own checks failed, the job failed -- surfacing it here means the
    caller sees a typed error rather than an artifact that looks authoritative.
    """
    validation = result.validation
    if validation is not None and not validation.valid:
        raise CadProviderError(
            result.provider.provider,
            "worker reported the geometry as invalid",
            details={"errors": validation.errors, "checks": validation.checks},
        )
    if not result.measurements:
        raise CadJobError("worker returned no measurements for a job that requested elements")
    for measurement in result.measurements:
        if not measurement.is_valid or not measurement.is_closed:
            raise CadProviderError(
                result.provider.provider,
                f"solid {measurement.id!r} is not a valid closed shell",
                details={
                    "is_valid": measurement.is_valid,
                    "is_closed": measurement.is_closed,
                    "solid_count": measurement.solid_count,
                },
            )


__all__ = [
    "KILL_GRACE_SECONDS",
    "WORKER_EXIT_OK",
    "WORKER_EXIT_REQUEST_ERROR",
    "run_cad_job",
]
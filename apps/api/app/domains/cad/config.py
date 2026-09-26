"""Configuration for the Phase 5 CAD/BIM pipeline.

Follows the same shape as :class:`app.domains.design.config.DesignEngineConfig`: a
frozen dataclass that owns the domain's tunables and can emit a ``canonical()``
dict for hashing into geometry provenance.

The dataclass deliberately contains only *policy*. Where the toolchain actually
lives on disk is resolved separately by
:mod:`app.domains.cad.capability`, because "what did we configure" and "what is
installed" are different questions and conflating them makes deployments
undebuggable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from app.core.config import Settings, get_settings

GeometryEngineName = Literal["cad_bim", "legacy"]
CadProviderName = Literal["auto", "freecad", "occt"]


@dataclass(frozen=True)
class CadConfig:
    """Resolved, validated policy for the CAD/BIM pipeline."""

    # Engine and provider selection
    geometry_engine: GeometryEngineName = "cad_bim"
    provider: CadProviderName = "auto"
    allow_legacy_engine: bool = True

    # Toolchain locations (empty string means "discover at runtime")
    worker_python: str = ""
    worker_venv_root: str = "H:/.cad-tools/worker-venv"
    freecad_root: str = "H:/.cad-tools/freecad-1.1.3/FreeCAD_1.1.3-Windows-x86_64-py311"
    artifact_root: str = "H:/.cad-tools/artifacts"

    # Resource limits. These are the containment boundary for a worker that is
    # processing attacker-influenced geometry, so they are deliberately
    # conservative and are enforced by the runner, not merely documented.
    job_timeout_seconds: float = 180.0
    freecad_timeout_seconds: float = 180.0
    worker_memory_limit_mb: int = 4096
    max_output_bytes: int = 67_108_864
    max_request_bytes: int = 1_048_576

    # Tessellation
    mesh_deflection_m: float = 0.05
    mesh_angular_deflection_rad: float = 0.35

    # Validation tolerances
    volume_tolerance_ratio: float = 0.005
    area_tolerance_ratio: float = 0.005
    linear_tolerance_m: float = 0.01

    # Artifact toggles
    ifc_schema: str = "IFC4"
    write_fcstd: bool = True
    write_step: bool = True
    write_ifc: bool = True
    write_glb: bool = True

    def __post_init__(self) -> None:
        """Reject a policy that cannot produce trustworthy geometry.

        :meth:`from_settings` validates the environment, but this dataclass is
        also constructed directly (``DEFAULT_CAD_CONFIG``, tests, embedded uses).
        A zero timeout or a negative payload limit is always a configuration
        mistake, and finding it here rather than as a mysteriously empty artifact
        later is the whole point of validating twice.
        """
        if self.geometry_engine not in ("cad_bim", "legacy"):
            raise ValueError(
                f"geometry_engine must be 'cad_bim' or 'legacy', got {self.geometry_engine!r}"
            )
        if self.provider not in ("auto", "freecad", "occt"):
            raise ValueError(f"provider must be 'auto', 'freecad' or 'occt', got {self.provider!r}")
        if not self.ifc_schema.startswith("IFC"):
            raise ValueError(f"ifc_schema must name an IFC schema such as IFC4, got {self.ifc_schema!r}")
        if self.job_timeout_seconds <= 0 or self.freecad_timeout_seconds <= 0:
            raise ValueError("job timeouts must be positive")
        if self.mesh_deflection_m <= 0 or self.mesh_angular_deflection_rad <= 0:
            raise ValueError("tessellation deflection must be positive")
        if self.max_request_bytes <= 0 or self.max_output_bytes <= 0:
            raise ValueError("payload limits must be positive")
        if self.max_request_bytes > self.max_output_bytes:
            raise ValueError("max_request_bytes cannot exceed max_output_bytes")
        if self.worker_memory_limit_mb <= 0:
            raise ValueError("worker_memory_limit_mb must be positive")
        for name in (
            "volume_tolerance_ratio",
            "area_tolerance_ratio",
            "linear_tolerance_m",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not self.allow_legacy_engine and self.geometry_engine == "legacy":
            raise ValueError("geometry_engine 'legacy' requires allow_legacy_engine=True")

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "CadConfig":
        """Build a :class:`CadConfig` from application settings."""
        s = settings or get_settings()
        engine = s.geometry_engine.strip().lower()
        if engine not in ("cad_bim", "legacy"):
            raise ValueError(
                f"GEOMETRY_ENGINE must be 'cad_bim' or 'legacy', got {s.geometry_engine!r}"
            )
        provider = s.cad_provider.strip().lower()
        if provider not in ("auto", "freecad", "occt"):
            raise ValueError(
                f"CAD_PROVIDER must be 'auto', 'freecad' or 'occt', got {s.cad_provider!r}"
            )
        if not s.cad_ifc_schema.startswith("IFC"):
            raise ValueError(
                f"CAD_IFC_SCHEMA must name an IFC schema such as IFC4, got {s.cad_ifc_schema!r}"
            )
        if s.cad_job_timeout_seconds <= 0 or s.cad_freecad_timeout_seconds <= 0:
            raise ValueError("CAD job timeouts must be positive")
        if s.cad_mesh_deflection_m <= 0:
            raise ValueError("CAD_MESH_DEFLECTION_M must be positive")
        if s.cad_max_request_bytes <= 0 or s.cad_max_output_bytes <= 0:
            raise ValueError("CAD payload limits must be positive")
        return cls(
            geometry_engine=engine,  # type: ignore[arg-type]
            provider=provider,  # type: ignore[arg-type]
            allow_legacy_engine=s.cad_allow_legacy_engine,
            worker_python=s.cad_worker_python,
            worker_venv_root=s.cad_worker_venv_root,
            freecad_root=s.cad_freecad_root,
            artifact_root=s.cad_artifact_root,
            job_timeout_seconds=s.cad_job_timeout_seconds,
            freecad_timeout_seconds=s.cad_freecad_timeout_seconds,
            worker_memory_limit_mb=s.cad_worker_memory_limit_mb,
            max_output_bytes=s.cad_max_output_bytes,
            max_request_bytes=s.cad_max_request_bytes,
            mesh_deflection_m=s.cad_mesh_deflection_m,
            mesh_angular_deflection_rad=s.cad_mesh_angular_deflection_rad,
            volume_tolerance_ratio=s.cad_volume_tolerance_ratio,
            area_tolerance_ratio=s.cad_area_tolerance_ratio,
            linear_tolerance_m=s.cad_linear_tolerance_m,
            ifc_schema=s.cad_ifc_schema,
            write_fcstd=s.cad_write_fcstd,
            write_step=s.cad_write_step,
            write_ifc=s.cad_write_ifc,
            write_glb=s.cad_write_glb,
        )

    @property
    def worker_site_packages(self) -> Path:
        """Return the worker virtualenv's site-packages directory."""
        return Path(self.worker_venv_root) / "Lib" / "site-packages"

    @property
    def resolved_freecad_cmd(self) -> Path:
        """Return the expected ``freecadcmd.exe`` path for the configured root.

        The portable build places the console executable in ``bin/``; the zip
        installer places it at the root. Both layouts are checked by capability
        detection, so this property only encodes the preferred location.
        """
        return Path(self.freecad_root) / "bin" / "freecadcmd.exe"

    def canonical(self) -> dict[str, str | float | int | bool]:
        """Return a stable dict of this config, suitable for provenance hashing."""
        return asdict(self)

    def toolchain_fingerprint(self) -> dict[str, str | float | int | bool]:
        """Return the subset of config that affects generated geometry.

        Deliberately excludes paths, timeouts, and toggles. Two runs that differ
        only in where the toolchain lives or how long it was allowed to run must
        produce the same geometry hash, otherwise the hash stops meaning
        "same building".
        """
        return {
            "provider": self.provider,
            "ifc_schema": self.ifc_schema,
            "mesh_deflection_m": self.mesh_deflection_m,
            "mesh_angular_deflection_rad": self.mesh_angular_deflection_rad,
            "volume_tolerance_ratio": self.volume_tolerance_ratio,
            "area_tolerance_ratio": self.area_tolerance_ratio,
            "linear_tolerance_m": self.linear_tolerance_m,
        }


DEFAULT_CAD_CONFIG = CadConfig()

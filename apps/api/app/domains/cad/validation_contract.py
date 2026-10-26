from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CadValidationContract:
    """Validated evidence required before CAD geometry becomes authoritative."""

    run_status: str
    validation: dict[str, Any]

    @property
    def valid(self) -> bool:
        return (
            self.run_status == "SUCCEEDED"
            and self.validation.get("valid") is True
            and isinstance(self.validation.get("checks"), list)
            and not self.validation.get("errors")
        )


def require_validated_cad_run(contract: CadValidationContract) -> None:
    if contract.run_status != "SUCCEEDED":
        raise ValueError("CAD_RUN_INVALID")
    if contract.validation.get("valid") is not True:
        raise ValueError("CAD_VALIDATION_REQUIRED")
    if not isinstance(contract.validation.get("checks"), list):
        raise ValueError("CAD_VALIDATION_INCOMPLETE")
    if contract.validation.get("errors"):
        raise ValueError("CAD_VALIDATION_FAILED")

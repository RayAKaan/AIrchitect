from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EngineeringFinding:
    code: str
    severity: str
    message: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EngineeringValidation:
    status: str
    findings: tuple[EngineeringFinding, ...]


def validate_screening_model(
    *, member_count: int, total_factored_load_kn: float, model_hash: str
) -> EngineeringValidation:
    """Validate structural screening inputs/results without claiming code compliance."""
    findings: list[EngineeringFinding] = []
    if not model_hash:
        findings.append(
            EngineeringFinding(
                "MODEL_HASH_MISSING", "ERROR", "Engineering result is not bound to a canonical model revision.", ()
            )
        )
    if member_count == 0:
        findings.append(
            EngineeringFinding(
                "NO_STRUCTURAL_MEMBERS", "ERROR", "No structural screening members were derived.", (model_hash,)
            )
        )
    if total_factored_load_kn < 0:
        findings.append(
            EngineeringFinding(
                "NEGATIVE_LOAD", "ERROR", "Factored gravity load cannot be negative.", (model_hash,)
            )
        )
    status = "INVALID" if any(item.severity == "ERROR" for item in findings) else "SCREENING_VALID"
    return EngineeringValidation(status, tuple(findings))

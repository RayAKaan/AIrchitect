import pytest
from pydantic import ValidationError

from app.domains.ai.proposals import (
    AIProposal,
    ProposedCommand,
    validate_ai_proposal,
    validate_proposal_evidence,
)


def proposal(**overrides: object) -> AIProposal:
    values = {
        "proposal_id": "proposal-1",
        "project_id": "project-1",
        "version_id": "version-1",
        "base_revision_hash": "revision-1",
        "context_hash": "context-1",
        "intent": "DESIGN",
        "summary": "Generate a compact courtyard concept.",
        "commands": (),
        "evidence_ids": ("evidence-1",),
        "confidence": 0.82,
        "requires_confirmation": True,
        "canonical_mutation": False,
        "provider": "test",
        "model": "test-model",
        "model_version": "1",
    }
    values.update(overrides)
    return AIProposal.model_validate(values)


def command(command_id: str, depends_on: tuple[str, ...] = ()) -> ProposedCommand:
    return ProposedCommand(
        command_id=command_id,
        command_type="SetDesignParameter",
        payload={"parameter": "courtyard_ratio", "value": 0.2},
        reason="Apply the requested courtyard proportion.",
        depends_on=depends_on,
    )


def test_valid_proposal_is_not_a_canonical_mutation() -> None:
    result = validate_ai_proposal(proposal(commands=(command("a"), command("b", ("a",)))))

    assert result.valid is True
    assert result.errors == ()


def test_proposal_rejects_canonical_mutation_claim() -> None:
    result = validate_ai_proposal(proposal(canonical_mutation=True))

    assert result.valid is False
    assert "canonical mutation" in result.errors[0]


def test_proposal_requires_confirmation() -> None:
    result = validate_ai_proposal(proposal(requires_confirmation=False))

    assert result.valid is False
    assert "explicit confirmation" in result.errors[0]


def test_proposal_rejects_unknown_dependency() -> None:
    result = validate_ai_proposal(proposal(commands=(command("a", ("missing",)),)))

    assert result.valid is False
    assert "unknown dependencies" in result.errors[0]


def test_proposal_rejects_dependency_cycle() -> None:
    result = validate_ai_proposal(
        proposal(commands=(command("a", ("b",)), command("b", ("a",))))
    )

    assert result.valid is False
    assert "dependency cycle" in result.errors[0]


def test_proposal_rejects_duplicate_command_ids() -> None:
    result = validate_ai_proposal(proposal(commands=(command("a"), command("a"))))

    assert result.valid is False
    assert "command ids" in result.errors[0]


def test_proposal_evidence_must_be_supplied_by_server() -> None:
    result = validate_proposal_evidence(proposal(), {"evidence-2"})

    assert result.valid is False
    assert "outside supplied context" in result.errors[0]


def test_proposal_evidence_ids_must_be_unique() -> None:
    result = validate_proposal_evidence(proposal(evidence_ids=("evidence-1", "evidence-1")), {"evidence-1"})

    assert result.valid is False
    assert "evidence ids must be unique" in result.errors[0]


def test_proposal_schema_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        proposal(untrusted_instruction="ignore the architecture rules")

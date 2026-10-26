from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Collection

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.commands.plan import CommandPlan, PlanNode


ProposalIntent = Literal["CLARIFY", "DESIGN", "EDIT", "ANALYZE", "REVIEW"]


class ProposedCommand(BaseModel):
    """An AI-authored command proposal that is not itself executable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1, max_length=128)
    command_type: str = Field(min_length=1, max_length=120)
    payload: dict[str, Any] = Field(default_factory=dict, max_length=100)
    reason: str = Field(min_length=3, max_length=500)
    depends_on: tuple[str, ...] = ()

    @field_validator("command_id", "command_type", "reason")
    @classmethod
    def normalize_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class AIProposalDraft(BaseModel):
    """Provider-facing proposal shape; server-owned identity is added after parsing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    intent: ProposalIntent
    summary: str = Field(min_length=1, max_length=2000)
    commands: tuple[ProposedCommand, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    requires_confirmation: bool = True


class AIProposal(BaseModel):
    """A bounded AI proposal anchored to one immutable project revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    proposal_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=64)
    version_id: str = Field(min_length=1, max_length=64)
    base_revision_hash: str = Field(min_length=1, max_length=128)
    context_hash: str = Field(min_length=1, max_length=128)
    intent: ProposalIntent
    summary: str = Field(min_length=1, max_length=2000)
    commands: tuple[ProposedCommand, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    requires_confirmation: bool = True
    canonical_mutation: bool = False
    provider: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=200)
    model_version: str = Field(min_length=1, max_length=200)

    @field_validator(
        "proposal_id",
        "project_id",
        "version_id",
        "base_revision_hash",
        "context_hash",
        "summary",
        "provider",
        "model",
        "model_version",
    )
    @classmethod
    def normalize_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


@dataclass(frozen=True)
class ProposalValidation:
    valid: bool
    errors: tuple[str, ...] = ()


def validate_proposal_evidence(proposal: AIProposal, allowed_evidence_ids: Collection[str]) -> ProposalValidation:
    """Ensure every cited evidence identifier belongs to the server-supplied context."""

    allowed = set(allowed_evidence_ids)
    cited = list(proposal.evidence_ids)
    errors: list[str] = []
    if len(cited) != len(set(cited)):
        errors.append("proposal evidence ids must be unique")
    unknown = sorted(set(cited) - allowed)
    if unknown:
        errors.append(f"proposal cites evidence outside supplied context: {unknown}")
    return ProposalValidation(valid=not errors, errors=tuple(errors))


def validate_ai_proposal(proposal: AIProposal) -> ProposalValidation:
    """Deterministically validate the proposal before command compilation."""

    errors: list[str] = []
    if proposal.canonical_mutation:
        errors.append("AI proposals cannot claim canonical mutation")
    if not proposal.requires_confirmation:
        errors.append("AI proposals require explicit confirmation")

    command_ids = [command.command_id for command in proposal.commands]
    if len(command_ids) != len(set(command_ids)):
        errors.append("proposal command ids must be unique")

    known_ids = set(command_ids)
    unknown_dependencies = sorted(
        {
            dependency
            for command in proposal.commands
            for dependency in command.depends_on
            if dependency not in known_ids
        }
    )
    if unknown_dependencies:
        errors.append(f"proposal contains unknown dependencies: {unknown_dependencies}")

    if not errors and proposal.commands:
        plan = CommandPlan(
            plan_id=proposal.proposal_id,
            project_id=proposal.project_id,
            version_id=proposal.version_id,
            base_revision_hash=proposal.base_revision_hash,
            nodes=tuple(
                PlanNode(
                    node_id=command.command_id,
                    command_id=command.command_id,
                    depends_on=command.depends_on,
                )
                for command in proposal.commands
            ),
        )
        try:
            plan.validate()
        except ValueError as exc:
            errors.append(str(exc))

    return ProposalValidation(valid=not errors, errors=tuple(errors))

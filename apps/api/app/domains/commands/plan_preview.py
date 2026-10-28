from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .contract import canonical_payload
from .impact import impact_for
from .plan import CommandPlan
from .plan_builder import build_sequential_plan
from .plan_fingerprint import fingerprint_plan
from .schemas import CommandEnvelope
from .service import validate_command


@dataclass(frozen=True)
class PlanPreview:
    plan: CommandPlan
    executable: bool
    execution_order: tuple[str, ...]
    command_ids: tuple[str, ...]
    impact_groups: tuple[str, ...]
    fingerprint: str | None
    validation_errors: tuple[str, ...]
    warnings: tuple[str, ...]


def preview_sequential_plan(plan_id: str, commands: Sequence[CommandEnvelope]) -> PlanPreview:
    errors: list[str] = []
    warnings: list[str] = []
    for command in commands:
        validation = validate_command(command)
        errors.extend(f"{command.command_id}: {error}" for error in validation.errors)
        warnings.extend(f"{command.command_id}: {warning}" for warning in validation.warnings)

    try:
        plan = build_sequential_plan(plan_id, commands)
    except ValueError as exc:
        return PlanPreview(
            plan=CommandPlan(plan_id, "", "", "", ()),
            executable=False,
            execution_order=(),
            command_ids=tuple(command.command_id for command in commands),
            impact_groups=(),
            fingerprint=None,
            validation_errors=tuple([*errors, str(exc)]),
            warnings=tuple(warnings),
        )

    if errors:
        return PlanPreview(
            plan=plan,
            executable=False,
            execution_order=plan.execution_order(),
            command_ids=tuple(command.command_id for command in commands),
            impact_groups=(),
            fingerprint=None,
            validation_errors=tuple(errors),
            warnings=tuple(warnings),
        )

    # Fingerprint exactly the normalized payload and command contract used at commit.
    command_payloads = {command.command_id: canonical_payload(command) for command in commands}
    command_types = {command.command_id: command.type for command in commands}
    schema_versions = {command.command_id: command.schema_version for command in commands}
    impact_groups = tuple(sorted({group for command in commands for group in impact_for(command)}))
    return PlanPreview(
        plan=plan,
        executable=True,
        execution_order=plan.execution_order(),
        command_ids=tuple(command.command_id for command in commands),
        impact_groups=impact_groups,
        fingerprint=fingerprint_plan(
            plan,
            command_payloads,
            command_types=command_types,
            schema_versions=schema_versions,
        ),
        validation_errors=(),
        warnings=tuple(warnings),
    )

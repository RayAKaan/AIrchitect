from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .schemas import CommandEnvelope, CommandValidationResult


Validator = Callable[[CommandEnvelope], CommandValidationResult]


@dataclass(frozen=True)
class CommandDefinition:
    name: str
    schema_version: int
    validator: Validator


class CommandRegistry:
    """Explicit registry for canonical mutations; unknown commands fail closed."""

    def __init__(self) -> None:
        self._definitions: dict[tuple[str, int], CommandDefinition] = {}

    def register(self, definition: CommandDefinition) -> None:
        key = (definition.name, definition.schema_version)
        if key in self._definitions:
            raise ValueError(f"command already registered: {definition.name}@{definition.schema_version}")
        self._definitions[key] = definition

    def get(self, name: str, schema_version: int) -> CommandDefinition | None:
        return self._definitions.get((name, schema_version))

    def validate(self, command: CommandEnvelope) -> CommandValidationResult:
        definition = self.get(command.type, command.schema_version)
        if definition is None:
            return CommandValidationResult(valid=False, errors=[f"unsupported command: {command.type}@{command.schema_version}"])
        return definition.validator(command)

    def names(self) -> list[str]:
        return sorted({definition.name for definition in self._definitions.values()})


def require_payload_keys(*keys: str) -> Validator:
    required = tuple(keys)

    def validate(command: CommandEnvelope) -> CommandValidationResult:
        missing = [key for key in required if key not in command.payload]
        return CommandValidationResult(
            valid=not missing,
            errors=[f"missing payload field: {key}" for key in missing],
        )

    return validate

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError

from .commands import ModelCommand, command_fingerprint
from .schemas import (
    ArchitecturalModel,
    Building,
    Door,
    Level,
    Site,
    Slab,
    Space,
    Stair,
    Wall,
    Window,
)

_ELEMENT_MODELS = {
    "site": Site,
    "building": Building,
    "level": Level,
    "space": Space,
    "wall": Wall,
    "door": Door,
    "window": Window,
    "slab": Slab,
    "stair": Stair,
}
_COLLECTIONS = {
    "building": "buildings",
    "level": "levels",
    "space": "spaces",
    "wall": "walls",
    "door": "doors",
    "window": "windows",
    "slab": "slabs",
    "stair": "stairs",
}


class ModelMutationError(ValueError):
    """Raised when a command cannot be applied without changing canonical state."""


def apply_commands(model: ArchitecturalModel, commands: Sequence[ModelCommand]) -> ArchitecturalModel:
    """Apply a complete command batch atomically and return the next model revision."""
    if not commands:
        return model

    seen_command_ids: set[str] = set()
    current = model
    for command in commands:
        if command.command_id in seen_command_ids:
            raise ModelMutationError(f"duplicate command_id: {command.command_id}")
        seen_command_ids.add(command.command_id)
        if command.expected_revision != model.revision:
            raise ModelMutationError(
                f"command {command.command_id} targets revision {command.expected_revision}, "
                f"but model is revision {model.revision}"
            )
        try:
            current = _apply_one(current, command)
        except (ValidationError, KeyError) as exc:
            raise ModelMutationError(f"command {command.command_id} is invalid: {exc}") from exc

    payload = current.model_dump(mode="json")
    payload["revision"] = model.revision + 1
    try:
        return ArchitecturalModel.model_validate(payload)
    except ValidationError as exc:
        raise ModelMutationError(f"command batch violates canonical model invariants: {exc}") from exc


def _apply_one(model: ArchitecturalModel, command: ModelCommand) -> ArchitecturalModel:
    if command.element_type == "site":
        if command.operation != "update" or command.element_id != model.site.id:
            raise ModelMutationError("site supports only update of the canonical site")
        site_payload = model.site.model_dump(mode="json")
        site_payload.update(command.payload)
        site_payload["id"] = model.site.id
        return _rebuild(model, site=Site.model_validate(site_payload))

    collection_name = _COLLECTIONS[command.element_type]
    collection = list(getattr(model, collection_name))
    index = next((index for index, item in enumerate(collection) if item.id == command.element_id), None)

    if command.operation == "create":
        if index is not None:
            raise ModelMutationError(f"element already exists: {command.element_id}")
        payload: dict[str, Any] = dict(command.payload)
        payload["id"] = command.element_id
        element = _ELEMENT_MODELS[command.element_type].model_validate(payload)
        collection.append(element)
    elif command.operation == "update":
        if index is None:
            raise ModelMutationError(f"element does not exist: {command.element_id}")
        payload = collection[index].model_dump(mode="json")
        payload.update(command.payload)
        payload["id"] = command.element_id
        collection[index] = _ELEMENT_MODELS[command.element_type].model_validate(payload)
    else:
        if index is None:
            raise ModelMutationError(f"element does not exist: {command.element_id}")
        collection.pop(index)

    return _rebuild(model, **{collection_name: tuple(collection)})


def _rebuild(model: ArchitecturalModel, **changes: Any) -> ArchitecturalModel:
    payload = model.model_dump(mode="json")
    payload.update(changes)
    return ArchitecturalModel.model_validate(payload)


def mutation_fingerprints(commands: Sequence[ModelCommand]) -> tuple[str, ...]:
    """Return command fingerprints in execution order for provenance/audit."""
    return tuple(command_fingerprint(command) for command in commands)

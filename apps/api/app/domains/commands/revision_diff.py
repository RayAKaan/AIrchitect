from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RevisionDiff:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]


def diff_semantic_models(before: dict[str, Any], after: dict[str, Any]) -> RevisionDiff:
    before_elements = _elements(before)
    after_elements = _elements(after)
    before_ids, after_ids = set(before_elements), set(after_elements)
    added = tuple(sorted(after_ids - before_ids))
    removed = tuple(sorted(before_ids - after_ids))
    changed = tuple(sorted(identifier for identifier in before_ids & after_ids if before_elements[identifier] != after_elements[identifier]))
    return RevisionDiff(added, removed, changed)


def _elements(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    semantic = model.get("semantic_model")
    raw = semantic.get("elements", []) if isinstance(semantic, dict) else []
    result: dict[str, dict[str, Any]] = {}
    for element in raw:
        if not isinstance(element, dict) or not isinstance(element.get("id"), str):
            continue
        result[element["id"]] = element
    return result

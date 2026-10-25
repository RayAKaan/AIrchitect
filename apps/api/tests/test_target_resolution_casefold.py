from __future__ import annotations

from app.domains.commands.target_resolution import resolve_target


def test_name_resolution_is_case_and_whitespace_stable() -> None:
    model = {"semantic_model": {"elements": [{"id": "b1", "type": "Building", "name": "Main Block"}]}}
    result = resolve_target(model, name="  main   block ", expected_type="Building")
    assert result.element_id == "b1"
    assert result.ambiguous is False

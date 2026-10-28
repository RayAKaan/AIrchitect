from __future__ import annotations

import pytest

from app.domains.commands.intent_parser import parse_intent
from app.domains.commands.intent_to_command import proposal_to_preview_command


def test_complete_supported_intent_becomes_canonical_preview_command() -> None:
    command = proposal_to_preview_command(
        parse_intent("resize the space 20 m2 id:s1"),
        project_id="p", version_id="v", base_revision_hash="h",
        command_id="c1", idempotency_key="abcdefgh", reason="Resize space",
    )
    assert command.type == "ResizeSpace"
    assert command.mode == "preview"
    assert command.payload["element_id"] == "s1"
    assert command.payload["area_m2"] == 20.0


def test_complete_but_unimplemented_intent_cannot_cross_command_boundary() -> None:
    with pytest.raises(ValueError, match="canonical mutation adapter"):
        proposal_to_preview_command(
            parse_intent("move the building 2 m x 3 m id:b1"),
            project_id="p", version_id="v", base_revision_hash="h",
            command_id="c1", idempotency_key="abcdefgh", reason="Move building",
        )


def test_incomplete_intent_cannot_cross_command_boundary() -> None:
    with pytest.raises(ValueError):
        proposal_to_preview_command(
            parse_intent("resize the space id:s1"),
            project_id="p", version_id="v", base_revision_hash="h",
            command_id="c1", idempotency_key="abcdefgh", reason="Resize",
        )

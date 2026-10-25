from __future__ import annotations

import pytest

from app.domains.commands.intent_parser import parse_intent
from app.domains.commands.intent_to_command import proposal_to_preview_command


def test_complete_intent_becomes_canonical_preview_command() -> None:
    command = proposal_to_preview_command(
        parse_intent("move the building 2 m x 3 m id:b1"),
        project_id="p", version_id="v", base_revision_hash="h",
        command_id="c1", idempotency_key="abcdefgh", reason="Move building",
    )
    assert command.type == "MoveBuilding"
    assert command.mode == "preview"
    assert command.payload["element_id"] == "b1"


def test_incomplete_intent_cannot_cross_command_boundary() -> None:
    with pytest.raises(ValueError):
        proposal_to_preview_command(
            parse_intent("resize the space id:s1"),
            project_id="p", version_id="v", base_revision_hash="h",
            command_id="c1", idempotency_key="abcdefgh", reason="Resize",
        )

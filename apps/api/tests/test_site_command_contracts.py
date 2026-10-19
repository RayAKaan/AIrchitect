from app.domains.site.schemas import SetSiteBoundaryCommand
from app.domains.site.service import _command_payload_hash


def test_set_site_boundary_command_requires_idempotency_and_boundary() -> None:
    command = SetSiteBoundaryCommand(command_id="cmd-1", idempotency_key="idem-1", boundary={"type": "Polygon", "coordinates": []})
    assert command.command_id == "cmd-1"
    assert command.idempotency_key == "idem-1"
    assert command.mode == "commit"


def test_idempotency_payload_hash_is_order_independent() -> None:
    boundary_a = {"type": "Polygon", "coordinates": [[[77.59, 12.97], [77.60, 12.97], [77.60, 12.98], [77.59, 12.97]]]}
    boundary_b = {"coordinates": boundary_a["coordinates"], "type": "Polygon"}
    assert _command_payload_hash(boundary_a, "Site", "reason") == _command_payload_hash(boundary_b, "Site", "reason")


def test_idempotency_payload_hash_changes_when_command_intent_changes() -> None:
    boundary = {"type": "Polygon", "coordinates": [[[77.59, 12.97], [77.60, 12.97], [77.60, 12.98], [77.59, 12.97]]]}
    first = _command_payload_hash(boundary, "Site", "reason")
    second = _command_payload_hash(boundary, "Different Site", "reason")
    assert first != second

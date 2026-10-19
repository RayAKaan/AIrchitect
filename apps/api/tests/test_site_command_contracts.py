from app.domains.site.schemas import SetSiteBoundaryCommand


def test_set_site_boundary_command_requires_idempotency_and_boundary() -> None:
    command = SetSiteBoundaryCommand(command_id="cmd-1", idempotency_key="idem-1", boundary={"type": "Polygon", "coordinates": []})
    assert command.command_id == "cmd-1"
    assert command.idempotency_key == "idem-1"
    assert command.mode == "commit"

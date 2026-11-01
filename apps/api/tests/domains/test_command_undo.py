from app.domains.commands.schemas import CommandEnvelope
from app.domains.commands.impact import impact_for
from app.domains.semantic_model.editing import impacts_for_history_event


def _command(command_type):
    return CommandEnvelope(
        command_id=f"{command_type.lower()}-1",
        type=command_type,
        schema_version=1,
        project_id="p",
        version_id="v",
        base_revision_hash="a" * 64,
        idempotency_key=f"{command_type.lower()}-12345678",
        payload={},
        reason=f"{command_type} last change",
    )


def test_undo_and_redo_preview_conservatively_invalidate_derived_outputs():
    for command_type in ("Undo", "Redo"):
        groups = set(impact_for(_command(command_type)))
        assert {
            "planning_envelope",
            "program",
            "design_alternatives",
            "parametric_geometry_intents",
            "quantities",
            "cost",
            "structural_review",
            "regulatory_review",
            "validation",
        } <= groups


def test_history_edit_reuses_precise_impact_groups():
    event = {
        "action": "EDIT",
        "impacts": ["parametric_geometry_intents", "quantities", "validation"],
    }
    assert impacts_for_history_event(event) == [
        "parametric_geometry_intents",
        "quantities",
        "validation",
    ]


def test_history_create_and_delete_events_receive_element_lifecycle_impacts():
    for action in ("CREATE", "DELETE"):
        groups = set(impacts_for_history_event({
            "action": action,
            "element_type": "Wall",
        }))
        assert {
            "parametric_geometry_intents",
            "quantities",
            "cost",
            "validation",
        } <= groups


def test_empty_history_impact_does_not_invent_a_target_event():
    assert impacts_for_history_event({"action": "LOCK"}) == []

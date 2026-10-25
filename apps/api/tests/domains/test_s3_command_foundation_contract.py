from app.domains.commands.batch import execute_command_batch
from app.domains.commands.contract import canonical_payload
from app.domains.commands.history_query import project_history
from app.domains.commands.intent_parser import parse_intent
from app.domains.commands.invalidation import invalidations_for
from app.domains.commands.preview_diff import explain_command
from app.domains.commands.preconditions import check_preconditions
from app.domains.commands.regeneration import build_regeneration_plan
from app.domains.commands.regeneration_engine import execution_steps


def test_s3_command_foundation_surfaces_are_importable():
    assert all((execute_command_batch, canonical_payload, project_history, parse_intent,
                 invalidations_for, explain_command, check_preconditions,
                 build_regeneration_plan, execution_steps))

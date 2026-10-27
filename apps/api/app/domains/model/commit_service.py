from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.model.change_impact import plan_change_impact

from .edit_batch import apply_edit_batch
from .edit_commands import EditCommand
from .persistence import CanonicalModelConflict, get_current_model, persist_model


async def commit_edit_batch(
    session: AsyncSession,
    *,
    project,
    version,
    actor_id: str,
    expected_revision: int,
    commands: tuple[EditCommand, ...],
    change_summary: str,
):
    current = await get_current_model(session, project.id)
    if current is None:
        raise CanonicalModelConflict("The project has no canonical architectural model")
    current_row, current_model = current
    if current_row.revision != expected_revision:
        raise CanonicalModelConflict(
            f"Expected model revision {expected_revision}, current revision is {current_row.revision}"
        )
    preview = apply_edit_batch(current_model, commands)
    impact = plan_change_impact(current_model, preview)
    row = await persist_model(
        session,
        project=project,
        version=version,
        model=preview,
        actor_id=actor_id,
        expected_revision=expected_revision,
        parent_revision_id=current_row.id,
        source="user_edit",
        change_summary=change_summary,
    )
    return row, preview, impact

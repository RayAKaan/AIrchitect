from app.domains.ai.proposals import AIProposal, ProposedCommand
from app.domains.ai.proposal_compiler import compile_proposal_commands


def base_proposal(commands: tuple[ProposedCommand, ...]) -> AIProposal:
    return AIProposal(
        proposal_id="proposal-1",
        project_id="project-1",
        version_id="version-1",
        base_revision_hash="revision-1",
        context_hash="context-1",
        intent="EDIT",
        summary="Update the courtyard program area.",
        commands=commands,
        confidence=0.9,
        provider="test",
        model="test-model",
        model_version="1",
    )


def command(command_id: str, depends_on: tuple[str, ...] = ()) -> ProposedCommand:
    return ProposedCommand(
        command_id=command_id,
        command_type="SetProgramArea",
        payload={"space_type": "courtyard", "area_m2": 120},
        reason="Apply the requested program area.",
        depends_on=depends_on,
    )


def test_compiler_emits_preview_only_commands() -> None:
    commands = compile_proposal_commands(base_proposal((command("a"), command("b", ("a",)))))

    assert [item.command_id for item in commands] == ["a", "b"]
    assert all(item.mode == "preview" for item in commands)
    assert all(item.project_id == "project-1" for item in commands)


def test_compiler_idempotency_is_stable() -> None:
    proposal = base_proposal((command("a"),))

    first = compile_proposal_commands(proposal)[0].idempotency_key
    second = compile_proposal_commands(proposal)[0].idempotency_key

    assert first == second
    assert first.startswith("ai-")


def test_compiler_rejects_unsupported_command() -> None:
    proposal = base_proposal(
        (
            ProposedCommand(
                command_id="a",
                command_type="UnsupportedAICommand",
                payload={},
                reason="Attempt an unsupported mutation.",
            ),
        )
    )

    try:
        compile_proposal_commands(proposal)
    except ValueError as exc:
        assert "unsupported commands" in str(exc)
    else:
        raise AssertionError("expected unsupported command rejection")

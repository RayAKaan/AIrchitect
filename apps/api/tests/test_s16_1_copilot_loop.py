from app.domains.ai.copilot_loop import CopilotLoop


def test_s16_copilot_loop_contract_is_immutable() -> None:
    assert CopilotLoop.__dataclass_params__.frozen is True
    assert {"proposal", "commands", "execution_order", "impact_groups", "plan_fingerprint", "approval_token"} == set(CopilotLoop.__dataclass_fields__)

import pytest
from app.domains.decisions.schemas import DecisionRequest
from app.domains.decisions.providers import DeterministicProvider, BenchmarkProvider, validated_decision, JevProvider

@pytest.fixture
def decision_input():
    return DecisionRequest(decision_type="routing", allowed_options=["clarify", "continue"])

@pytest.mark.asyncio
async def test_deterministic_provider_is_repeatable_by_policy(decision_input):
    result = await validated_decision(DeterministicProvider(), decision_input)
    assert result.selected_option == "clarify"
    assert result.fallback_used is True
    assert result.confidence is None

@pytest.mark.asyncio
async def test_benchmark_fixture(decision_input):
    result = await validated_decision(BenchmarkProvider({"routing": "continue"}), decision_input)
    assert result.selected_option == "continue"
    assert result.provider == "benchmark-fixture"

@pytest.mark.asyncio
async def test_benchmark_missing_fixture_fails(decision_input):
    with pytest.raises(ValueError):
        await BenchmarkProvider().decide(decision_input)

@pytest.mark.asyncio
async def test_jev_fails_closed(decision_input):
    with pytest.raises(RuntimeError, match="not configured"):
        await JevProvider().decide(decision_input)

@pytest.mark.asyncio
async def test_invalid_provider_option_rejected(decision_input):
    class InvalidProvider:
        async def decide(self, req):
            from app.domains.decisions.schemas import DecisionResponse
            return DecisionResponse(decision_id="x", selected_option="unsafe", rationale="x",
                provider="test", provider_version="1", validation_status="unchecked")
    with pytest.raises(ValueError, match="outside allowed_options"):
        await validated_decision(InvalidProvider(), decision_input)

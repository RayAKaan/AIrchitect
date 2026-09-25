from abc import ABC, abstractmethod
from uuid import uuid4
from app.domains.decisions.schemas import DecisionRequest, DecisionResponse

class DecisionProvider(ABC):
    name = "abstract"
    version = "1"

    @abstractmethod
    async def decide(self, request: DecisionRequest) -> DecisionResponse: ...

class DeterministicProvider(DecisionProvider):
    """Safe reproducible default: select first allowed option; no engineering inference."""
    name = "deterministic-local"
    version = "1.0.0"

    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        return DecisionResponse(
            decision_id=request.decision_id or str(uuid4()),
            selected_option=request.allowed_options[0], confidence=None,
            rationale="Deterministic fallback selected the first caller-ordered allowed option; this is not a quality ranking.",
            provider=self.name, provider_version=self.version,
            validation_status="validated", fallback_used=True,
            metadata={"selection_policy": "first_allowed_option"},
        )

class BenchmarkProvider(DecisionProvider):
    name = "benchmark-fixture"
    version = "1.0.0"

    def __init__(self, fixtures: dict[str, str] | None = None):
        self.fixtures = fixtures or {}

    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        selected = self.fixtures.get(request.decision_type)
        if selected not in request.allowed_options:
            raise ValueError("No valid benchmark fixture for this decision type")
        return DecisionResponse(decision_id=request.decision_id or str(uuid4()), selected_option=selected,
            confidence=None, rationale="Recorded benchmark fixture; not a live model judgment.",
            provider=self.name, provider_version=self.version, validation_status="validated",
            metadata={"fixture": True})

class JevProvider(DecisionProvider):
    """Deliberately fails closed until a documented, configured Jev contract is supplied."""
    name = "jev"
    version = "unconfigured"

    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        raise RuntimeError("Jev adapter is not configured; no undocumented API contract will be assumed")

async def validated_decision(provider: DecisionProvider, request: DecisionRequest) -> DecisionResponse:
    response = await provider.decide(request)
    if response.selected_option not in request.allowed_options:
        raise ValueError("Provider selected an option outside allowed_options")
    if response.decision_id != (request.decision_id or response.decision_id):
        raise ValueError("Provider decision_id mismatch")
    return response

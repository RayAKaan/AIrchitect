from fastapi import APIRouter, Depends, HTTPException
from app.core.config import settings
from app.dependencies import current_user
from app.db.models import User
from app.domains.decisions.schemas import DecisionRequest, DecisionResponse
from app.domains.decisions.providers import DeterministicProvider, BenchmarkProvider, JevProvider, validated_decision

router = APIRouter(prefix="/decisions", tags=["decisions"])

@router.post("/evaluate", response_model=DecisionResponse)
async def evaluate(body: DecisionRequest, user: User = Depends(current_user)) -> DecisionResponse:
    provider_name = settings.decision_provider.lower()
    provider = {"deterministic": DeterministicProvider(), "local": DeterministicProvider(),
                "benchmark": BenchmarkProvider(), "jev": JevProvider()}.get(provider_name)
    if provider is None:
        raise HTTPException(503, "Configured decision provider is unsupported")
    try:
        result = await validated_decision(provider, body)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return result

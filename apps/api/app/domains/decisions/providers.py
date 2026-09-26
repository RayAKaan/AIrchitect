import json
from abc import ABC, abstractmethod
from uuid import uuid4
import httpx
from app.core.config import get_settings
from app.domains.decisions.schemas import DecisionRequest, DecisionResponse

class DecisionProvider(ABC):
    name = "abstract"
    version = "1"
    @abstractmethod
    async def decide(self, request: DecisionRequest) -> DecisionResponse: ...

class DeterministicProvider(DecisionProvider):
    """Safe reproducible fallback. Caller ordering is policy, never an inferred quality ranking."""
    name="deterministic-local"; version="1.0.0"
    async def decide(self,request:DecisionRequest)->DecisionResponse:
        return DecisionResponse(decision_id=request.decision_id or str(uuid4()),selected_option=request.allowed_options[0],confidence=None,rationale="Deterministic fallback selected the first policy-allowed option; this is not a quality ranking.",provider=self.name,provider_version=self.version,validation_status="validated",fallback_used=True,metadata={"selection_policy":"first_allowed_option"})

class BenchmarkProvider(DecisionProvider):
    name="benchmark-fixture"; version="1.0.0"
    def __init__(self,fixtures:dict[str,str]|None=None): self.fixtures=fixtures or {}
    async def decide(self,request:DecisionRequest)->DecisionResponse:
        selected=self.fixtures.get(request.decision_type)
        if selected not in request.allowed_options: raise ValueError("No valid benchmark fixture for this decision type")
        return DecisionResponse(decision_id=request.decision_id or str(uuid4()),selected_option=selected,confidence=None,rationale="Recorded benchmark fixture; not a live model judgment.",provider=self.name,provider_version=self.version,validation_status="validated",metadata={"fixture":True})

class JevProvider(DecisionProvider):
    """TypeSafe System One adapter using the documented Choice, Score, and Noul contract."""
    name="jev"; version="systemone-v1"
    def __init__(self)->None:
        s=get_settings(); self.key=s.jev_api_key; self.model=s.jev_model; self.base=s.jev_base_url.rstrip('/'); self.timeout=s.jev_timeout_seconds
    @property
    def available(self)->bool: return bool(self.key and get_settings().jev_enabled)
    async def decide(self,request:DecisionRequest)->DecisionResponse:
        if not self.available: raise RuntimeError("JEV_PROVIDER_UNAVAILABLE: Jev is not configured")
        primitive=str(request.metadata.get("jev_primitive","choice")).lower()
        instructions=str(request.metadata.get("instructions") or f"Select the most suitable bounded route for {request.decision_type}.")
        if primitive=="choice":
            descriptions=request.metadata.get("option_descriptions",{})
            question={"type":"choice","instructions":instructions,"criteria":{o:str(descriptions.get(o,o)) for o in request.allowed_options}}
        elif primitive=="score":
            criteria=request.metadata.get("score_criteria")
            if not isinstance(criteria,list) or len(criteria)!=len(request.allowed_options): raise ValueError("score_criteria must align with allowed_options")
            question={"type":"score","instructions":instructions,"criteria":criteria}
        elif primitive=="noul":
            if len(request.allowed_options)!=2 or not request.metadata.get("yes_option") or not request.metadata.get("no_option"): raise ValueError("Noul requires two options and explicit yes_option/no_option")
            question={"type":"noul","instructions":instructions}
        else: raise ValueError("Unsupported Jev primitive")
        state=json.dumps({"context":request.context,"constraints":request.constraints},sort_keys=True,separators=(',',':'))
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response=await client.post(f"{self.base}/v1/systemone",headers={"Authorization":f"Bearer {self.key}","Content-Type":"application/json"},json={"state":state,"model":self.model,"questions":{"decision":question}})
        response.raise_for_status(); data=response.json(); answer=data["answers"]["decision"]
        if answer.get("type")!=primitive: raise ValueError("Jev response primitive mismatch")
        probabilities=answer.get("probabilities",{})
        if primitive=="choice": selected=answer["choice"]
        elif primitive=="score": selected=request.allowed_options[max(0,min(len(request.allowed_options)-1,round(float(answer["score"]))))]
        else: selected=request.metadata["yes_option"] if float(answer["noul"])>=float(request.metadata.get("noul_threshold",.5)) else request.metadata["no_option"]
        usage=data.get("usage",{})
        return DecisionResponse(decision_id=request.decision_id or str(uuid4()),selected_option=selected,confidence=answer.get("confidence"),rationale="TypeSafe Jev bounded recommendation; deterministic policy remains authoritative.",provider=self.name,provider_version=data.get("model",self.model),validation_status="validated",metadata={"primitive":primitive,"probabilities":probabilities,"request_id":response.headers.get("x-request-id"),"usage":usage,"actual_model":data.get("model")})

async def validated_decision(provider:DecisionProvider,request:DecisionRequest)->DecisionResponse:
    response=await provider.decide(request)
    if response.selected_option not in request.allowed_options: raise ValueError("Provider selected an option outside allowed_options")
    if response.decision_id!=(request.decision_id or response.decision_id): raise ValueError("Provider decision_id mismatch")
    return response

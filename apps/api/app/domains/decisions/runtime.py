from dataclasses import dataclass
from time import perf_counter
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.db.models import DecisionRecord,Project,ProjectVersion
from app.domains.lifecycle.service import canonical_hash
from .providers import DecisionProvider,DeterministicProvider,JevProvider,validated_decision
from .schemas import DecisionRequest,DecisionResponse

@dataclass(frozen=True)
class PolicyOutcome:
 selected_option:str
 disposition:str
 reason:str

class DecisionPolicyEngine:
 def apply(self,request:DecisionRequest,recommendation:DecisionResponse)->PolicyOutcome:
  invalid=set(request.constraints.get('invalid_options',[]))
  blockers=request.constraints.get('hard_blockers',[])
  if blockers:
   if 'BLOCK' not in request.allowed_options: raise ValueError('Hard blockers exist and no BLOCK route is allowed')
   return PolicyOutcome('BLOCK','POLICY_OVERRIDE','Deterministic hard blockers require BLOCK routing.')
  if recommendation.selected_option in invalid: raise ValueError('Provider recommendation conflicts with deterministic constraints')
  threshold=float(request.constraints.get('review_confidence_threshold',0))
  if recommendation.confidence is not None and recommendation.confidence<threshold and 'REVIEW' in request.allowed_options:
   return PolicyOutcome('REVIEW','LOW_CONFIDENCE_ROUTE','Confidence affected routing only; it did not establish correctness.')
  return PolicyOutcome(recommendation.selected_option,'ACCEPTED_RECOMMENDATION','Recommendation passed deterministic policy constraints.')

class DecisionRuntime:
 def __init__(self,policy:DecisionPolicyEngine|None=None): self.policy=policy or DecisionPolicyEngine()
 def provider(self)->DecisionProvider:
  name=get_settings().decision_provider.lower()
  if name in {'deterministic','local'}: return DeterministicProvider()
  if name=='jev': return JevProvider()
  if name=='auto': return JevProvider() if JevProvider().available else DeterministicProvider()
  raise RuntimeError('DECISION_PROVIDER_UNSUPPORTED')
 async def evaluate(self,session:AsyncSession,request:DecisionRequest,project:Project|None=None,workflow_id:str|None=None,step_id:str|None=None)->DecisionResponse:
  provider=self.provider(); started=perf_counter(); provider_error={}
  try: response=await validated_decision(provider,request)
  except Exception as exc:
   if get_settings().decision_provider.lower()!='auto' or isinstance(provider,DeterministicProvider): raise
   provider_error={'provider':provider.name,'error_class':type(exc).__name__}; response=await validated_decision(DeterministicProvider(),request)
  outcome=self.policy.apply(request,response); response.selected_option=outcome.selected_option; response.metadata.update({'policy_disposition':outcome.disposition,'policy_reason':outcome.reason})
  response.validation_status='policy_validated'
  if request.project_version_id:
   usage=response.metadata.get('usage',{}); probabilities=response.metadata.get('probabilities',{})
   session.add(DecisionRecord(organization_id=project.organization_id if project else None,project_id=project.id if project else None,project_version_id=request.project_version_id,workflow_id=workflow_id,step_id=step_id,decision_type=request.decision_type,provider=response.provider,provider_model=response.metadata.get('actual_model',''),provider_version=response.provider_version,input_hash=canonical_hash({'context':request.context,'constraints':request.constraints,'options':request.allowed_options}),inputs_json=request.model_dump(mode='json'),outputs_json=response.model_dump(mode='json'),decision=response.selected_option,probabilities_json=probabilities,confidence=response.confidence,latency_ms=round((perf_counter()-started)*1000),input_tokens=usage.get('input_tokens'),output_tokens=usage.get('output_tokens'),request_id=response.metadata.get('request_id'),fallback_used=response.fallback_used or bool(provider_error),provider_error_json=provider_error,final_disposition=outcome.disposition))
  return response

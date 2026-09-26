from time import perf_counter
from typing import Any,TypeVar
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.db.models import LLMUsageRecord,Project
from app.domains.lifecycle.service import canonical_hash
from .providers import LLMProvider,get_llm_provider
T=TypeVar('T',bound=BaseModel)

class LLMRuntime:
 def __init__(self,provider:LLMProvider|None=None):self.provider=provider or get_llm_provider()
 async def structured(self,session:AsyncSession,*,project:Project,version_id:str|None,workflow_id:str|None,operation:str,instructions:str,context:dict[str,Any],schema:type[T],prompt_version:str)->T:
  settings=get_settings(); serialized=str(context)
  if len(serialized)>settings.llm_max_input_tokens*4: raise ValueError('AI_CONTEXT_BUDGET_EXCEEDED')
  started=perf_counter(); input_hash=canonical_hash(context); result=None; error=None
  try:
   result=await self.provider.structured(operation=operation,instructions=instructions,context=context,schema=schema)
   parsed=schema.model_validate(result.content)
  except Exception as exc:
   error=type(exc).__name__
   session.add(LLMUsageRecord(organization_id=project.organization_id,project_id=project.id,project_version_id=version_id,workflow_id=workflow_id,provider=self.provider.name,model='',operation=operation,prompt_version=prompt_version,schema_version='1.0.0',request_id='failed-'+input_hash[:16],input_hash=input_hash,context_hash=input_hash,status='FAILED',latency_ms=round((perf_counter()-started)*1000),error_code=error,output_json={},provenance_json={'context_minimized':True}))
   raise
  total=(result.input_tokens or 0)+(result.output_tokens or 0); estimated=((result.input_tokens or 0)*settings.llm_input_cost_per_million_usd+(result.output_tokens or 0)*settings.llm_output_cost_per_million_usd)/1_000_000
  session.add(LLMUsageRecord(organization_id=project.organization_id,project_id=project.id,project_version_id=version_id,workflow_id=workflow_id,provider=result.provider,model=result.model,model_version=result.model_version,operation=operation,prompt_version=prompt_version,schema_version=str(result.content.get('schema_version','1.0.0')),request_id=result.request_id,input_hash=input_hash,context_hash=input_hash,output_hash=canonical_hash(result.content),status='SUCCEEDED',input_tokens=result.input_tokens,output_tokens=result.output_tokens,total_tokens=total,latency_ms=round((perf_counter()-started)*1000),estimated_cost_usd=estimated,actual_cost_usd=result.actual_cost_usd,output_json=result.content,provenance_json={'context_minimized':True,'provider_metadata':result.raw_metadata}))
  return parsed

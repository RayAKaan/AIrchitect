import json
from abc import ABC,abstractmethod
from typing import Any,TypeVar
from uuid import uuid4
import httpx
from pydantic import BaseModel
from app.core.config import get_settings
from .schemas import ProviderResult

T=TypeVar('T',bound=BaseModel)

class LLMProvider(ABC):
    name:str
    @abstractmethod
    async def structured(self,*,operation:str,instructions:str,context:dict[str,Any],schema:type[T]) -> ProviderResult: ...
    def status(self)->dict[str,Any]: return {'provider':self.name,'available':True}

class DeterministicLLMProvider(LLMProvider):
    name='deterministic'
    async def structured(self,*,operation:str,instructions:str,context:dict[str,Any],schema:type[T])->ProviderResult:
        # Explicit offline adapter: it validates deterministic engine output; it does not imitate a remote model.
        output=context.get('deterministic_output',{})
        validated=schema.model_validate(output)
        return ProviderResult(content=validated.model_dump(mode='json'),provider=self.name,model='deterministic-local',model_version='1.0.0',request_id=f'local-{uuid4()}')

class OpenAICompatibleLLMProvider(LLMProvider):
    name='openai-compatible'
    def __init__(self)->None:
        s=get_settings(); self.model=s.llm_model; self.key=s.llm_api_key; self.base=s.llm_base_url.rstrip('/'); self.timeout=s.llm_timeout_seconds
    def status(self)->dict[str,Any]: return {'provider':self.name,'available':bool(self.key),'model':self.model,'reason':None if self.key else 'API key not configured'}
    async def structured(self,*,operation:str,instructions:str,context:dict[str,Any],schema:type[T])->ProviderResult:
        if not self.key: raise RuntimeError('LLM_PROVIDER_UNAVAILABLE')
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response=await client.post(f'{self.base}/chat/completions',headers={'Authorization':f'Bearer {self.key}','Content-Type':'application/json'},json={'model':self.model,'temperature':0,'messages':[{'role':'system','content':instructions},{'role':'user','content':json.dumps(context,separators=(',',':'))}], 'response_format':{'type':'json_schema','json_schema':{'name':operation,'strict':True,'schema':schema.model_json_schema()}}})
        response.raise_for_status(); data=response.json(); choice=data['choices'][0]['message']['content']; parsed=schema.model_validate_json(choice)
        usage=data.get('usage',{})
        return ProviderResult(content=parsed.model_dump(mode='json'),provider=self.name,model=data.get('model',self.model),model_version=data.get('system_fingerprint') or '',request_id=response.headers.get('x-request-id',data.get('id',str(uuid4()))),input_tokens=usage.get('prompt_tokens'),output_tokens=usage.get('completion_tokens'),raw_metadata={'finish_reason':data['choices'][0].get('finish_reason')})

def get_llm_provider()->LLMProvider:
    name=get_settings().llm_provider.lower()
    if name=='deterministic': return DeterministicLLMProvider()
    if name in {'openai','openai-compatible'}: return OpenAICompatibleLLMProvider()
    raise RuntimeError(f'Unsupported LLM provider: {name}')

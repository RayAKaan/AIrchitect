from typing import Any,Literal
from pydantic import BaseModel,Field

class ExtractedFact(BaseModel):
 parameter:str
 value:Any=None
 unit:str|None=None
 confidence:float=Field(ge=0,le=1)
 source_text:str
class ClarificationQuestion(BaseModel):
 id:str
 parameter:str
 question:str
 reason:str
 priority:Literal['LOW','MEDIUM','HIGH','CRITICAL']
class AssumptionProposal(BaseModel):
 parameter:str
 proposed_value:Any
 unit:str|None=None
 rationale:str
 requires_confirmation:bool=True
class BuildingBriefExtraction(BaseModel):
 schema_version:str='1.0.0'
 facts:list[ExtractedFact]=Field(default_factory=list)
 ambiguities:list[str]=Field(default_factory=list)
 clarifications:list[ClarificationQuestion]=Field(default_factory=list)
 assumptions:list[AssumptionProposal]=Field(default_factory=list)
 injection_detected:bool=False
class WorkflowPlan(BaseModel):
 schema_version:str='1.0.0'
 recommended_route:Literal['DESIGN','ENGINEERING','REGULATORY','REVIEW','CLARIFICATION','BLOCK']
 reasons:list[str]
 required_steps:list[str]
class ChangeImpactExplanation(BaseModel):
 schema_version:str='1.0.0'
 summary:str
 changed_fields:list[str]
 affected_artifacts:list[str]
 evidence_ids:list[str]
class FeasibilityNarrative(BaseModel):
 schema_version:str='1.0.0'
 summary:str
 limitations:list[str]
 unknowns:list[str]
 evidence_ids:list[str]
 grounding_status:Literal['GROUNDED','UNGROUNDED','REVIEW_REQUIRED']='REVIEW_REQUIRED'
class IntakeRequest(BaseModel):
 text:str=Field(min_length=1,max_length=50000)
 version_ref:str|None=None
class ClarificationRequest(BaseModel):
 version_ref:str
 answers:dict[str,Any]
class AssistantRequest(BaseModel):
 question:str=Field(min_length=1,max_length=4000)
 version_ref:str|None=None
class ProviderResult(BaseModel):
 content:dict[str,Any]|None=None
 text:str|None=None
 provider:str
 model:str
 model_version:str
 request_id:str
 input_tokens:int|None=None
 output_tokens:int|None=None
 actual_cost_usd:float|None=None
 raw_metadata:dict[str,Any]=Field(default_factory=dict)

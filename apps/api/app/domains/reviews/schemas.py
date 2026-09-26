from typing import Literal
from pydantic import BaseModel,Field
class ReviewCreate(BaseModel):
 project_id:str
 project_version_id:str|None=None
 workflow_id:str|None=None
 artifact_id:str=Field(min_length=1,max_length=128)
 artifact_version:str=Field(min_length=1,max_length=128)
 artifact_version_ids:list[str]=Field(default_factory=list)
 world_model_version:str=''
 source_hash:str=Field(min_length=1,max_length=256)
 decision:Literal['ACCEPT_FOR_FEASIBILITY','REQUEST_CHANGES','BLOCK']
 rationale:str=Field(min_length=5,max_length=4000)
 comments:str=''
class ReviewOut(BaseModel):
 id:str;project_id:str;project_version_id:str|None=None;workflow_id:str|None=None;artifact_id:str;artifact_version:str;source_hash:str;reviewer_user_id:str;decision:str;rationale:str;comments:str='';created_at:str
class DeliverableCreate(BaseModel):
 project_id:str
 artifact_id:str=Field(min_length=1,max_length=128)
 artifact_version:str=Field(min_length=1,max_length=128)
 source_hash:str=Field(min_length=1,max_length=256)
 title:str=Field(min_length=1,max_length=200)
 summary:str=Field(min_length=1,max_length=5000)
 sections:dict=Field(default_factory=dict)
 validation_status:Literal['ready_for_review','blocked','stale','incomplete']
 current:bool

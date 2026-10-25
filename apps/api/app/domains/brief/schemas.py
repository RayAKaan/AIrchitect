from pydantic import BaseModel, Field

class BriefWrite(BaseModel):
    raw_text: str = Field(min_length=10, max_length=50000)
    source_type: str = Field(default="USER_BRIEF", min_length=1, max_length=40)
    source_reference: str | None = Field(default=None, max_length=500)
    structured: dict = Field(default_factory=dict)

class BriefOut(BaseModel):
    id: str
    project_id: str
    project_version_id: str
    revision: int
    raw_text: str
    structured: dict
    source_type: str
    source_reference: str | None
    content_hash: str
    created_at: str

class BriefHistoryOut(BaseModel):
    project_version_id: str
    revisions: list[BriefOut]

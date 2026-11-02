from pydantic import BaseModel, Field


class AlternativeSelection(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class AlternativeApproval(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)
    comments: str = Field(default="", max_length=4000)

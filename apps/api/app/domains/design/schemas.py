from pydantic import BaseModel, Field


class AlternativeSelection(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)

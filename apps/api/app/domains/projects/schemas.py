from pydantic import BaseModel, Field

class ProjectCreate(BaseModel):
    organization_id: str
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    building_type: str = Field(default="commercial", pattern="^(commercial|retail)$")
    location: str = Field(default="Saudi Arabia", max_length=200)

class ProjectOut(BaseModel):
    id: str
    organization_id: str
    name: str
    description: str
    building_type: str
    location: str
    status: str
    version: int
    created_by: str

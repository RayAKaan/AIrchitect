from pydantic import BaseModel, Field, model_validator


class ArtifactNode(BaseModel):
    artifact_id: str = Field(min_length=1, max_length=160)
    artifact_type: str = Field(min_length=1, max_length=80)
    revision: str = Field(min_length=1, max_length=160)
    depends_on: list[str] = Field(default_factory=list)
    status: str = Field(default="current", pattern="^(current|stale|blocked|unknown)$")


class ChangeImpactRequest(BaseModel):
    project_id: str
    changed_artifact_ids: list[str] = Field(min_length=1)
    new_source_revision: str = Field(min_length=1, max_length=160)
    artifacts: list[ArtifactNode] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_graph(self):
        ids = [n.artifact_id for n in self.artifacts]
        if len(ids) != len(set(ids)):
            raise ValueError("artifact_id values must be unique")
        known = set(ids)
        if not set(self.changed_artifact_ids) <= known:
            raise ValueError("changed_artifact_ids must reference supplied artifacts")
        for node in self.artifacts:
            if node.artifact_id in node.depends_on:
                raise ValueError("artifact cannot depend on itself")
            if not set(node.depends_on) <= known:
                raise ValueError(f"unknown dependency for {node.artifact_id}")
        return self


class ImpactedArtifact(BaseModel):
    artifact_id: str
    artifact_type: str
    previous_status: str
    resulting_status: str
    reason: str
    dependency_path: list[str]


class ChangeImpactResponse(BaseModel):
    project_id: str
    source_revision: str
    impacted: list[ImpactedArtifact]
    unchanged_artifact_ids: list[str]
    evaluation_status: str = "impact_analysis_only"
    disclaimer: str = "Impact analysis only; no artifact was recomputed or independently verified."

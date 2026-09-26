from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(timezone.utc)


def uid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Membership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_user"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(24), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    building_type: Mapped[str] = mapped_column(String(40), default="commercial")
    location: Mapped[str] = mapped_column(String(200), default="Saudi Arabia")
    status: Mapped[str] = mapped_column(String(24), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)  # compatibility/current version number
    current_version_id: Mapped[str | None] = mapped_column(ForeignKey("project_versions.id", use_alter=True,
        name="fk_projects_current_version"), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ProjectVersion(Base):
    __tablename__ = "project_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_project_version"),
        UniqueConstraint("project_id", "idempotency_key", name="uq_project_version_idempotency"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    revision_number: Mapped[int] = mapped_column(Integer, default=1)
    change_summary: Mapped[str] = mapped_column(Text, default="Initial version")
    parent_version_id: Mapped[str | None] = mapped_column(ForeignKey("project_versions.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(80), default="user")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BuildingBriefRecord(Base):
    __tablename__ = "building_briefs"
    __table_args__ = (UniqueConstraint("project_version_id", "revision", name="uq_brief_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    raw_text: Mapped[str] = mapped_column(Text)
    structured_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source_type: Mapped[str] = mapped_column(String(40), default="USER_BRIEF")
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RequirementRecord(Base):
    __tablename__ = "requirements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id", ondelete="CASCADE"), index=True)
    source_text: Mapped[str] = mapped_column(Text)
    parameter: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(60))
    raw_value_json: Mapped[object] = mapped_column(JSON, nullable=True)
    extracted_value_json: Mapped[object] = mapped_column(JSON, nullable=True)
    normalized_value_json: Mapped[object] = mapped_column(JSON, nullable=True)
    value_type: Mapped[str] = mapped_column(String(24), default="string")
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), default="USER_BRIEF")
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(100), default="deterministic_pattern_v2")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="EXTRACTED")
    contradiction_group: Mapped[str | None] = mapped_column(String(80), nullable=True)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("requirements.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class AssumptionRecord(Base):
    __tablename__ = "assumptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str | None] = mapped_column(ForeignKey("project_versions.id"), nullable=True, index=True)
    project_version: Mapped[int] = mapped_column(Integer, default=1)
    parameter: Mapped[str] = mapped_column(String(120))
    value_json: Mapped[dict] = mapped_column(JSON)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(500), default="system-proposed")
    status: Mapped[str] = mapped_column(String(24), default="proposed")
    impact_scope_json: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("assumptions.id"), nullable=True)


class WorldModelRevision(Base):
    __tablename__ = "world_model_revisions"
    __table_args__ = (UniqueConstraint("project_id", "revision", name="uq_world_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str | None] = mapped_column(ForeignKey("project_versions.id"), nullable=True, index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    model_json: Mapped[dict] = mapped_column(JSON)
    model_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(80), default="requirements_and_assumptions")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"
    __table_args__ = (UniqueConstraint("project_version_id", "artifact_type", "version", name="uq_artifact_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id", ondelete="CASCADE"), index=True)
    world_model_revision_id: Mapped[str | None] = mapped_column(ForeignKey("world_model_revisions.id"), nullable=True)
    alternative_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    artifact_type: Mapped[str] = mapped_column(String(60), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="current", index=True)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    input_references_json: Mapped[list] = mapped_column(JSON, default=list)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ArtifactDependency(Base):
    __tablename__ = "artifact_dependencies"
    __table_args__ = (UniqueConstraint("artifact_version_id", "depends_on_artifact_version_id", name="uq_artifact_dependency"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    artifact_version_id: Mapped[str] = mapped_column(ForeignKey("artifact_versions.id", ondelete="CASCADE"), index=True)
    depends_on_artifact_version_id: Mapped[str] = mapped_column(ForeignKey("artifact_versions.id", ondelete="CASCADE"), index=True)
    dependency_kind: Mapped[str] = mapped_column(String(40), default="input")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DomainArtifactMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    artifact_version_id: Mapped[str] = mapped_column(ForeignKey("artifact_versions.id", ondelete="CASCADE"), unique=True, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id", ondelete="CASCADE"), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DesignGenerationRun(Base):
    __tablename__ = "design_generation_runs"
    __table_args__ = (UniqueConstraint("project_version_id", "generation_key", name="uq_design_generation_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id", ondelete="CASCADE"), index=True)
    world_model_revision_id: Mapped[str] = mapped_column(ForeignKey("world_model_revisions.id"), index=True)
    world_model_hash: Mapped[str] = mapped_column(String(64), index=True)
    generation_key: Mapped[str] = mapped_column(String(64))
    engine_version: Mapped[str] = mapped_column(String(40))
    config_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="GENERATING", index=True)
    progress_json: Mapped[list] = mapped_column(JSON, default=list)
    generated_alternative_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DesignConstraintRecord(Base):
    __tablename__ = "design_constraints"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    generation_run_id: Mapped[str] = mapped_column(ForeignKey("design_generation_runs.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id", ondelete="CASCADE"), index=True)
    world_model_revision_id: Mapped[str] = mapped_column(ForeignKey("world_model_revisions.id"), index=True)
    source_reference: Mapped[str] = mapped_column(String(160))
    parameter: Mapped[str] = mapped_column(String(100), index=True)
    value_json: Mapped[object] = mapped_column(JSON, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    classification: Mapped[str] = mapped_column(String(24))
    operator: Mapped[str] = mapped_column(String(24))
    severity: Mapped[str] = mapped_column(String(24))
    rationale: Mapped[str] = mapped_column(Text)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DesignAlternative(Base, DomainArtifactMixin):
    __tablename__ = "design_alternatives"
    __table_args__ = (UniqueConstraint("project_version_id", "design_hash", name="uq_design_hash_per_version"),)
    world_model_revision_id: Mapped[str | None] = mapped_column(ForeignKey("world_model_revisions.id"), nullable=True, index=True)
    generation_run_id: Mapped[str | None] = mapped_column(ForeignKey("design_generation_runs.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    strategy_id: Mapped[str] = mapped_column(String(80), default="legacy")
    strategy_version: Mapped[str] = mapped_column(String(40), default="1")
    design_parameters_json: Mapped[dict] = mapped_column(JSON)
    key_metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    constraint_results_json: Mapped[list] = mapped_column(JSON, default=list)
    reasoning_json: Mapped[dict] = mapped_column(JSON, default=dict)
    assumptions_json: Mapped[list] = mapped_column(JSON, default=list)
    unknowns_json: Mapped[list] = mapped_column(JSON, default=list)
    tradeoffs_json: Mapped[list] = mapped_column(JSON, default=list)
    design_engine_version: Mapped[str] = mapped_column(String(40), default="legacy")
    design_engine_config_version: Mapped[str] = mapped_column(String(40), default="legacy")
    input_world_model_hash: Mapped[str] = mapped_column(String(64), default="")
    design_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="GENERATING", index=True)
    selected_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    selection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class GeometryArtifact(Base, DomainArtifactMixin):
    __tablename__ = "geometry_artifacts"
    __table_args__ = (UniqueConstraint("project_version_id", "geometry_hash", name="uq_geometry_hash_per_version"),)
    alternative_id: Mapped[str] = mapped_column(ForeignKey("design_alternatives.id"), index=True)
    world_model_revision_id: Mapped[str | None] = mapped_column(ForeignKey("world_model_revisions.id"), nullable=True, index=True)
    geometry_hash: Mapped[str] = mapped_column(String(64), index=True)
    input_world_model_hash: Mapped[str] = mapped_column(String(64), default="")
    design_hash: Mapped[str] = mapped_column(String(64), default="")
    engine_name: Mapped[str] = mapped_column(String(80), default="legacy")
    engine_version: Mapped[str] = mapped_column(String(40), default="legacy")
    status: Mapped[str] = mapped_column(String(24), default="CURRENT", index=True)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class QuantityArtifact(Base, DomainArtifactMixin):
    __tablename__ = "quantity_artifacts"
    __table_args__ = (UniqueConstraint("project_version_id", "quantity_hash", name="uq_quantity_hash_per_version"),)
    world_model_revision_id: Mapped[str | None] = mapped_column(ForeignKey("world_model_revisions.id"), nullable=True, index=True)
    design_alternative_id: Mapped[str | None] = mapped_column(ForeignKey("design_alternatives.id"), nullable=True, index=True)
    geometry_artifact_id: Mapped[str] = mapped_column(ForeignKey("geometry_artifacts.id"), index=True)
    input_world_model_hash: Mapped[str] = mapped_column(String(64), default="")
    input_design_hash: Mapped[str] = mapped_column(String(64), default="")
    input_geometry_hash: Mapped[str] = mapped_column(String(64), default="")
    engine_name: Mapped[str] = mapped_column(String(80), default="legacy")
    engine_version: Mapped[str] = mapped_column(String(40), default="legacy")
    config_version: Mapped[str] = mapped_column(String(40), default="legacy")
    quantity_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="CURRENT", index=True)
    assumptions_json: Mapped[list] = mapped_column(JSON, default=list)
    unknowns_json: Mapped[list] = mapped_column(JSON, default=list)
    uncertainty_json: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class RateSchedule(Base):
    __tablename__ = "rate_schedules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(40))
    geography: Mapped[str] = mapped_column(String(120))
    jurisdiction: Mapped[str] = mapped_column(String(120), default="unspecified")
    currency: Mapped[str] = mapped_column(String(3), default="SAR")
    source: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(32), default="USER_PROVIDED")
    source_reference: Mapped[str] = mapped_column(String(500), default="")
    source_date: Mapped[str] = mapped_column(String(40))
    effective_date: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    rates_json: Mapped[list] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RateEntry(Base):
    __tablename__ = "rate_entries"
    __table_args__ = (UniqueConstraint("rate_schedule_id", "item_code", name="uq_rate_entry_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    rate_schedule_id: Mapped[str] = mapped_column(ForeignKey("rate_schedules.id", ondelete="CASCADE"), index=True)
    item_code: Mapped[str] = mapped_column(String(80), index=True)
    category: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(240))
    unit: Mapped[str] = mapped_column(String(40))
    rate: Mapped[float] = mapped_column(Float)
    low_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="SAR")
    source_type: Mapped[str] = mapped_column(String(32))
    source_reference: Mapped[str] = mapped_column(String(500))
    effective_date: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[str] = mapped_column(String(32), default="USER_DECLARED")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class CostEstimate(Base, DomainArtifactMixin):
    __tablename__ = "cost_estimates"
    __table_args__ = (UniqueConstraint("project_version_id", "cost_hash", name="uq_cost_hash_per_version"),)
    world_model_revision_id: Mapped[str | None] = mapped_column(ForeignKey("world_model_revisions.id"), nullable=True, index=True)
    design_alternative_id: Mapped[str | None] = mapped_column(ForeignKey("design_alternatives.id"), nullable=True, index=True)
    geometry_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("geometry_artifacts.id"), nullable=True, index=True)
    quantity_artifact_id: Mapped[str] = mapped_column(ForeignKey("quantity_artifacts.id"), index=True)
    rate_schedule_id: Mapped[str] = mapped_column(ForeignKey("rate_schedules.id"), index=True)
    input_quantity_hash: Mapped[str] = mapped_column(String(64), default="")
    input_rate_schedule_hash: Mapped[str] = mapped_column(String(64), default="")
    engine_name: Mapped[str] = mapped_column(String(80), default="legacy")
    engine_version: Mapped[str] = mapped_column(String(40), default="legacy")
    config_version: Mapped[str] = mapped_column(String(40), default="legacy")
    cost_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="SAR")
    direct_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    low_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="CURRENT", index=True)
    assumptions_json: Mapped[list] = mapped_column(JSON, default=list)
    unknowns_json: Mapped[list] = mapped_column(JSON, default=list)
    uncertainty_json: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class StructuralArtifact(Base, DomainArtifactMixin):
    __tablename__ = "structural_artifacts"
    __table_args__ = (UniqueConstraint("project_version_id", "concept_hash", name="uq_structural_hash_per_version"),)
    world_model_revision_id: Mapped[str | None] = mapped_column(ForeignKey("world_model_revisions.id"), nullable=True, index=True)
    design_alternative_id: Mapped[str | None] = mapped_column(ForeignKey("design_alternatives.id"), nullable=True, index=True)
    geometry_artifact_id: Mapped[str] = mapped_column(ForeignKey("geometry_artifacts.id"), index=True)
    input_world_model_hash: Mapped[str] = mapped_column(String(64), default="")
    input_design_hash: Mapped[str] = mapped_column(String(64), default="")
    input_geometry_hash: Mapped[str] = mapped_column(String(64), default="")
    engine_name: Mapped[str] = mapped_column(String(80), default="legacy")
    engine_version: Mapped[str] = mapped_column(String(40), default="legacy")
    config_version: Mapped[str] = mapped_column(String(40), default="legacy")
    concept_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="CURRENT", index=True)
    assumptions_json: Mapped[list] = mapped_column(JSON, default=list)
    warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    unknowns_json: Mapped[list] = mapped_column(JSON, default=list)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class RegulatoryRuleset(Base):
    __tablename__ = "regulatory_rulesets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    jurisdiction: Mapped[str] = mapped_column(String(120))
    authority: Mapped[str] = mapped_column(String(200), default="unconfigured")
    source: Mapped[str] = mapped_column(String(500))
    source_reference: Mapped[str] = mapped_column(String(500))
    source_version: Mapped[str] = mapped_column(String(80))
    effective_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    version: Mapped[str] = mapped_column(String(40))
    authoritative: Mapped[bool] = mapped_column(Boolean, default=False)


class RegulatoryRule(Base):
    __tablename__ = "regulatory_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    ruleset_id: Mapped[str] = mapped_column(ForeignKey("regulatory_rulesets.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    parameter: Mapped[str] = mapped_column(String(100), default="")
    operator: Mapped[str] = mapped_column(String(24), default="exists")
    threshold_json: Mapped[object] = mapped_column(JSON, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    applicability_json: Mapped[dict] = mapped_column(JSON, default=dict)
    expression_json: Mapped[dict] = mapped_column(JSON)
    source_reference: Mapped[str] = mapped_column(String(500), default="")
    effective_date: Mapped[str] = mapped_column(String(40), default="")


class RegulatoryEvaluation(Base, DomainArtifactMixin):
    __tablename__ = "regulatory_evaluations"
    __table_args__ = (UniqueConstraint("project_version_id", "regulatory_hash", name="uq_regulatory_hash_per_version"),)
    world_model_revision_id: Mapped[str | None] = mapped_column(ForeignKey("world_model_revisions.id"), nullable=True, index=True)
    design_alternative_id: Mapped[str | None] = mapped_column(ForeignKey("design_alternatives.id"), nullable=True, index=True)
    geometry_artifact_id: Mapped[str] = mapped_column(ForeignKey("geometry_artifacts.id"), index=True)
    ruleset_id: Mapped[str | None] = mapped_column(ForeignKey("regulatory_rulesets.id"), nullable=True, index=True)
    input_world_model_hash: Mapped[str] = mapped_column(String(64), default="")
    input_design_hash: Mapped[str] = mapped_column(String(64), default="")
    input_geometry_hash: Mapped[str] = mapped_column(String(64), default="")
    engine_name: Mapped[str] = mapped_column(String(80), default="legacy")
    engine_version: Mapped[str] = mapped_column(String(40), default="legacy")
    config_version: Mapped[str] = mapped_column(String(40), default="legacy")
    regulatory_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="UNKNOWN", index=True)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class RegulatoryResult(Base):
    __tablename__ = "regulatory_results"
    __table_args__ = (UniqueConstraint("evaluation_id", "rule_code", name="uq_regulatory_result_rule"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("regulatory_evaluations.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[str | None] = mapped_column(ForeignKey("regulatory_rules.id"), nullable=True)
    rule_code: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    applicability: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), index=True)
    observed_json: Mapped[object] = mapped_column(JSON, nullable=True)
    threshold_json: Mapped[object] = mapped_column(JSON, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    calculation: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ValidationRun(Base, DomainArtifactMixin):
    __tablename__ = "validation_runs"
    __table_args__ = (UniqueConstraint("project_version_id", "validation_hash", name="uq_validation_hash_per_version"),)
    world_model_revision_id: Mapped[str | None] = mapped_column(ForeignKey("world_model_revisions.id"), nullable=True, index=True)
    design_alternative_id: Mapped[str | None] = mapped_column(ForeignKey("design_alternatives.id"), nullable=True, index=True)
    input_hashes_json: Mapped[dict] = mapped_column(JSON, default=dict)
    engine_name: Mapped[str] = mapped_column(String(80), default="legacy")
    engine_version: Mapped[str] = mapped_column(String(40), default="legacy")
    config_version: Mapped[str] = mapped_column(String(40), default="legacy")
    validation_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="BLOCKED", index=True)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ValidationCheck(Base):
    __tablename__ = "validation_checks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    validation_run_id: Mapped[str] = mapped_column(ForeignKey("validation_runs.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(24), default="INFO")
    category: Mapped[str] = mapped_column(String(60), default="GENERAL")
    status: Mapped[str] = mapped_column(String(24))
    message: Mapped[str] = mapped_column(Text)
    source_artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    evidence_ids_json: Mapped[list] = mapped_column(JSON, default=list)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    artifact_version_id: Mapped[str] = mapped_column(ForeignKey("artifact_versions.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(60))
    source_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_hash: Mapped[str] = mapped_column(String(64))
    source_version: Mapped[str] = mapped_column(String(80))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    content_hash: Mapped[str] = mapped_column(String(64))
    verification_method: Mapped[str] = mapped_column(String(100))
    verified_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(24), default="unverified")


class DecisionRecord(Base):
    __tablename__ = "decision_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id"), index=True)
    workflow_id: Mapped[str | None] = mapped_column(ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True, index=True)
    step_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_tasks.id", ondelete="SET NULL"), nullable=True)
    decision_type: Mapped[str] = mapped_column(String(80), default="LEGACY", index=True)
    provider: Mapped[str] = mapped_column(String(80))
    provider_model: Mapped[str] = mapped_column(String(120), default="")
    provider_version: Mapped[str] = mapped_column(String(80))
    input_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    question_schema_version: Mapped[str] = mapped_column(String(40), default="1.0.0")
    inputs_json: Mapped[dict] = mapped_column(JSON)
    outputs_json: Mapped[dict] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String(100), default="")
    probabilities_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_error_json: Mapped[dict] = mapped_column(JSON, default=dict)
    human_override_json: Mapped[dict] = mapped_column(JSON, default=dict)
    final_disposition: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkflowRecord(Base):
    __tablename__ = "workflows"
    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key", name="uq_workflow_idempotency"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str | None] = mapped_column(ForeignKey("project_versions.id"), nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    workflow_type: Mapped[str] = mapped_column(String(100))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(24), default="CREATED", index=True)
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    workflow_definition_version: Mapped[str] = mapped_column(String(40), default="legacy")
    failure_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class WorkflowTaskRecord(Base):
    __tablename__ = "workflow_tasks"
    __table_args__ = (UniqueConstraint("workflow_id", "key", name="uq_workflow_task_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(100))
    payload_json: Mapped[dict] = mapped_column(JSON)
    depends_on_json: Mapped[list] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(24), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    failure_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_version_id: Mapped[str | None] = mapped_column(ForeignKey("artifact_versions.id"), nullable=True, index=True)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(160), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_tasks.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80))
    from_state: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_state: Mapped[str] = mapped_column(String(24))
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LLMUsageRecord(Base):
    __tablename__ = "llm_usage_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str | None] = mapped_column(ForeignKey("project_versions.id"), nullable=True, index=True)
    workflow_id: Mapped[str | None] = mapped_column(ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(120), default="")
    operation: Mapped[str] = mapped_column(String(80), index=True)
    prompt_version: Mapped[str] = mapped_column(String(80))
    schema_version: Mapped[str] = mapped_column(String(40))
    request_id: Mapped[str] = mapped_column(String(160))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    context_hash: Mapped[str] = mapped_column(String(64), default="")
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class EvidenceNode(Base):
    __tablename__ = "evidence_nodes"
    __table_args__ = (UniqueConstraint("project_version_id", "evidence_hash", name="uq_evidence_hash_per_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id", ondelete="CASCADE"), index=True)
    workflow_id: Mapped[str | None] = mapped_column(ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True, index=True)
    source_id: Mapped[str] = mapped_column(String(160), index=True)
    source_type: Mapped[str] = mapped_column(String(60), index=True)
    source_hash: Mapped[str] = mapped_column(String(64))
    evidence_hash: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(240))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class EvidenceLink(Base):
    __tablename__ = "evidence_links"
    __table_args__ = (UniqueConstraint("from_node_id", "to_node_id", "relation", name="uq_evidence_link"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id", ondelete="CASCADE"), index=True)
    from_node_id: Mapped[str] = mapped_column(ForeignKey("evidence_nodes.id", ondelete="CASCADE"), index=True)
    to_node_id: Mapped[str] = mapped_column(ForeignKey("evidence_nodes.id", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DecisionEvaluation(Base):
    __tablename__ = "decision_evaluations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    decision_record_id: Mapped[str] = mapped_column(ForeignKey("decision_records.id", ondelete="CASCADE"), index=True)
    decision_type: Mapped[str] = mapped_column(String(80), index=True)
    input_context_hash: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    decision: Mapped[str] = mapped_column(String(100))
    deterministic_outcome: Mapped[str] = mapped_column(String(100))
    human_outcome: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agreement: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReviewRecord(Base):
    __tablename__ = "feasibility_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str | None] = mapped_column(ForeignKey("project_versions.id"), nullable=True, index=True)
    workflow_id: Mapped[str | None] = mapped_column(ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True, index=True)
    artifact_versions_json: Mapped[list] = mapped_column(JSON, default=list)
    world_model_version: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(32), default="REVIEWED", index=True)
    artifact_id: Mapped[str] = mapped_column(String(128), index=True)
    artifact_version: Mapped[str] = mapped_column(String(128))
    source_hash: Mapped[str] = mapped_column(String(256))
    reviewer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reviewer_role: Mapped[str] = mapped_column(String(24), default="reviewer")
    decision: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(Text)
    comments: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DeliverableRecord(Base):
    __tablename__ = "feasibility_deliverables"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    project_version_id: Mapped[str | None] = mapped_column(ForeignKey("project_versions.id"), nullable=True, index=True)
    artifact_id: Mapped[str] = mapped_column(String(128))
    artifact_version: Mapped[str] = mapped_column(String(128))
    source_hash: Mapped[str] = mapped_column(String(256))
    format: Mapped[str] = mapped_column(String(16))
    payload_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default="generated")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DeliverableArtifact(Base):
    __tablename__ = "deliverable_artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    deliverable_id: Mapped[str] = mapped_column(ForeignKey("feasibility_deliverables.id", ondelete="CASCADE"), index=True)
    artifact_version_id: Mapped[str] = mapped_column(ForeignKey("artifact_versions.id"), index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    project_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor_user_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(60))
    resource_id: Mapped[str] = mapped_column(String(36))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

from contextlib import asynccontextmanager
import logging
import re
from time import perf_counter
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings, validate_production_settings
from app.core.observability import clear_context, configure_logging, log_event, new_context, set_context
from app.core.security import hash_password, verify_password, issue_token
from app.db.models import User, Organization, Membership, Project, AuditEvent
from app.domains.foundation.service import create_initial_state
from app.db.session import get_engine, get_session, dispose_engine
from app.dependencies import current_user, require_membership
from app.domains.identity.schemas import RegisterRequest, LoginRequest, AuthOut, UserOut
from app.domains.projects.schemas import ProjectCreate, ProjectOut

configure_logging()
logger = logging.getLogger("airchitect.api")

@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_production_settings(settings)
    try:
        yield
    finally:
        await dispose_engine()

app = FastAPI(title=settings.app_name, version="0.4.0", lifespan=lifespan)

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_CONTEXT_HEADER_MAP = {
    "X-Project-Id": "project_id",
    "X-Revision-Id": "revision_id",
    "X-Command-Id": "command_id",
    "X-Generation-Id": "generation_id",
}


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied_id = request.headers.get("X-Request-Id", "")
    request_id = supplied_id if _REQUEST_ID_PATTERN.fullmatch(supplied_id) else str(uuid4())
    context = new_context(request_id)
    request.state.request_id = request_id
    for header, field in _CONTEXT_HEADER_MAP.items():
        value = request.headers.get(header)
        if value and _REQUEST_ID_PATTERN.fullmatch(value):
            set_context(**{field: value})
    started = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = round((perf_counter() - started) * 1000, 2)
        log_event(logger, "http.request.completed", method=request.method, path=request.url.path, status_code=status_code, duration_ms=duration_ms)
        if "response" in locals():
            response.headers["X-Request-Id"] = context.request_id
            for header, field in _CONTEXT_HEADER_MAP.items():
                value = getattr(context, field)
                if value: response.headers[header] = value
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
            response.headers["Cache-Control"] = "no-store"
        clear_context()


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or new_context().request_id
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        payload = exc.detail
        payload["error"].setdefault("request_id", request_id)
    else:
        code = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT"}.get(exc.status_code, "REQUEST_ERROR")
        payload = {"error": {"code": code, "message": str(exc.detail), "request_id": request_id}}
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.get("/health", tags=["operations"])
async def health() -> dict[str, str]: return {"status": "ok", "service": "api"}

@app.get("/ready", tags=["operations"])
async def readiness() -> JSONResponse:
    try:
        async with get_engine().connect() as connection: await connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable"})
    return JSONResponse(content={"status": "ready", "database": "available"})

@app.get(f"{settings.api_prefix}/system", tags=["operations"])
async def system_info() -> dict[str, str]: return {"name": settings.app_name, "environment": settings.app_env, "decision_provider": settings.decision_provider}

@app.post(f"{settings.api_prefix}/auth/register", response_model=AuthOut, status_code=201, tags=["identity"])
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)) -> AuthOut:
    email = str(body.email).lower(); user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password)); session.add(user)
    try:
        await session.flush(); org = Organization(name=body.organization_name.strip(), created_by=user.id); session.add(org); await session.flush()
        session.add(Membership(organization_id=org.id, user_id=user.id, role="owner")); session.add(AuditEvent(organization_id=org.id, actor_user_id=user.id, action="organization.created", resource_type="organization", resource_id=org.id)); await session.commit()
    except IntegrityError:
        await session.rollback(); raise HTTPException(409, "An account with this email already exists") from None
    return AuthOut(access_token=issue_token(user.id), user=UserOut(id=user.id, email=user.email, name=user.name))

@app.post(f"{settings.api_prefix}/auth/login", response_model=AuthOut, tags=["identity"])
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> AuthOut:
    user = await session.scalar(select(User).where(User.email == str(body.email).lower()))
    if user is None or not verify_password(body.password, user.password_hash): raise HTTPException(401, "Invalid email or password")
    set_context(actor_id=user.id); return AuthOut(access_token=issue_token(user.id), user=UserOut(id=user.id, email=user.email, name=user.name))

@app.get(f"{settings.api_prefix}/auth/me", response_model=UserOut, tags=["identity"])
async def me(user: User = Depends(current_user)) -> UserOut: set_context(actor_id=user.id); return UserOut(id=user.id, email=user.email, name=user.name)

@app.get(f"{settings.api_prefix}/organizations", tags=["organizations"])
async def list_organizations(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict[str, str]]:
    set_context(actor_id=user.id); rows = await session.execute(select(Organization, Membership.role).join(Membership).where(Membership.user_id == user.id)); return [{"id": org.id, "name": org.name, "role": role} for org, role in rows]

@app.post(f"{settings.api_prefix}/projects", response_model=ProjectOut, status_code=201, tags=["projects"])
async def create_project(body: ProjectCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> Project:
    set_context(actor_id=user.id); await require_membership(body.organization_id, user, session, {"owner", "admin", "member"}); project = Project(organization_id=body.organization_id, name=body.name.strip(), description=body.description, building_type=body.building_type, location=body.location, created_by=user.id); session.add(project); await session.flush(); set_context(project_id=project.id, revision_id=project.current_version_id); await create_initial_state(session, project, user.id); session.add(AuditEvent(organization_id=project.organization_id, project_id=project.id, project_version_id=project.current_version_id, actor_user_id=user.id, action="PROJECT_CREATED", resource_type="project", resource_id=project.id)); await session.commit(); await session.refresh(project); return project

@app.get(f"{settings.api_prefix}/projects", response_model=list[ProjectOut], tags=["projects"])
async def list_projects(organization_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[Project]:
    set_context(actor_id=user.id); await require_membership(organization_id, user, session); result = await session.scalars(select(Project).where(Project.organization_id == organization_id).order_by(Project.updated_at.desc())); return list(result.all())

@app.get(f"{settings.api_prefix}/projects/{{project_id}}", response_model=ProjectOut, tags=["projects"])
async def get_project(project_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> Project:
    set_context(actor_id=user.id, project_id=project_id); project = await session.get(Project, project_id)
    if project is None: raise HTTPException(404, "Project not found")
    await require_membership(project.organization_id, user, session); set_context(revision_id=project.current_version_id); return project

@app.patch(f"{settings.api_prefix}/projects/{{project_id}}", response_model=ProjectOut, tags=["projects"])
async def update_project(project_id: str, body: ProjectCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> Project:
    set_context(actor_id=user.id, project_id=project_id); project = await session.get(Project, project_id)
    if project is None: raise HTTPException(404, "Project not found")
    membership = await require_membership(project.organization_id, user, session, {"owner", "admin", "member"})
    if body.organization_id != project.organization_id: raise HTTPException(422, "Project organization cannot be changed")
    if membership.role == "viewer": raise HTTPException(403, "Viewer cannot edit projects")
    if body.building_type != project.building_type or body.location != project.location: raise HTTPException(409, {"error": {"code": "CANONICAL_VERSION_REQUIRED", "message": "Building type/location changes must create a new canonical project version."}})
    project.name, project.description = body.name.strip(), body.description; session.add(AuditEvent(organization_id=project.organization_id, project_id=project.id, project_version_id=project.current_version_id, actor_user_id=user.id, action="PROJECT_UPDATED", resource_type="project", resource_id=project.id)); await session.commit(); await session.refresh(project); set_context(revision_id=project.current_version_id); return project

from app.domains.world_model.routes import router as world_model_router
app.include_router(world_model_router, prefix=settings.api_prefix)
from app.domains.semantic_model.routes import router as semantic_model_router
app.include_router(semantic_model_router, prefix=settings.api_prefix)
from app.domains.requirements.routes import router as requirements_router
app.include_router(requirements_router, prefix=settings.api_prefix)
from app.domains.assumptions.routes import router as assumptions_router
app.include_router(assumptions_router, prefix=settings.api_prefix)
from app.domains.decisions.routes import router as decisions_router
app.include_router(decisions_router, prefix=settings.api_prefix)
from app.domains.workflows.routes import router as workflows_router
app.include_router(workflows_router, prefix=settings.api_prefix)
from app.domains.geometry.routes import router as geometry_router
app.include_router(geometry_router, prefix=settings.api_prefix)
from app.domains.estimates.routes import router as estimates_router
app.include_router(estimates_router, prefix=settings.api_prefix)
from app.domains.structure.routes import router as structure_router
app.include_router(structure_router, prefix=settings.api_prefix)
from app.domains.regulatory.routes import router as regulatory_router
app.include_router(regulatory_router, prefix=settings.api_prefix)
from app.domains.change_impact.routes import router as change_impact_router
app.include_router(change_impact_router, prefix=settings.api_prefix)
from app.domains.validation.routes import router as validation_router
app.include_router(validation_router, prefix=settings.api_prefix)
from app.domains.reviews.routes import router as reviews_router
app.include_router(reviews_router, prefix=settings.api_prefix)
from app.domains.foundation.routes import router as foundation_router
app.include_router(foundation_router, prefix=settings.api_prefix)
from app.domains.design.routes import router as design_router
app.include_router(design_router, prefix=settings.api_prefix)
from app.domains.design.system_preview_routes import router as system_preview_router
app.include_router(system_preview_router, prefix=settings.api_prefix)
from app.domains.cad.routes import router as cad_router
app.include_router(cad_router, prefix=settings.api_prefix)
from app.domains.engineering.routes import router as engineering_router
app.include_router(engineering_router, prefix=settings.api_prefix)
from app.domains.lifecycle.routes import router as lifecycle_router
app.include_router(lifecycle_router, prefix=settings.api_prefix)
from app.domains.lifecycle.runtime_routes import router as runtime_router
app.include_router(runtime_router, prefix=settings.api_prefix)
from app.domains.ai.routes import router as ai_router
app.include_router(ai_router, prefix=settings.api_prefix)
from app.domains.evidence.routes import router as evidence_router
app.include_router(evidence_router, prefix=settings.api_prefix)
from app.domains.site.routes import router as site_router
app.include_router(site_router, prefix=settings.api_prefix)
from app.domains.commands.routes import router as commands_router
app.include_router(commands_router, prefix=settings.api_prefix)
from app.domains.model.transform_routes import router as transform_router
app.include_router(transform_router, prefix=settings.api_prefix)
from app.domains.model.persistence_routes import router as model_persistence_router
app.include_router(model_persistence_router, prefix=settings.api_prefix)
from app.domains.model.edit_routes import router as model_edit_router
app.include_router(model_edit_router, prefix=settings.api_prefix)
from app.domains.cad_exchange.routes import router as cad_exchange_router
app.include_router(cad_exchange_router, prefix=settings.api_prefix)

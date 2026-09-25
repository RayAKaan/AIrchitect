from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings, validate_production_settings
from app.core.security import hash_password, verify_password, issue_token
from app.db.models import Base, User, Organization, Membership, Project, AuditEvent
from app.db.session import get_engine, get_session, dispose_engine
from app.dependencies import current_user, require_membership
from app.domains.identity.schemas import RegisterRequest, LoginRequest, AuthOut, UserOut
from app.domains.projects.schemas import ProjectCreate, ProjectOut

@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_production_settings(settings)
    # Convenient local bootstrap; production schema changes must use Alembic migrations.
    if settings.app_env == "local":
        try:
            async with get_engine().begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        except Exception:
            # API health remains available while dependencies are starting; /ready reports DB failure.
            pass
    try:
        yield
    finally:
        await dispose_engine()

app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)

@app.get("/health", tags=["operations"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}

@app.get("/ready", tags=["operations"])
async def readiness() -> JSONResponse:
    try:
        async with get_engine().connect() as connection: await connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable"})
    return JSONResponse(content={"status": "ready", "database": "available"})

@app.get(f"{settings.api_prefix}/system", tags=["operations"])
async def system_info() -> dict[str, str]:
    return {"name": settings.app_name, "environment": settings.app_env, "decision_provider": settings.decision_provider}

@app.post(f"{settings.api_prefix}/auth/register", response_model=AuthOut, status_code=201, tags=["identity"])
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)) -> AuthOut:
    email = str(body.email).lower()
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    session.add(user)
    try:
        await session.flush()
        org = Organization(name=body.organization_name.strip(), created_by=user.id)
        session.add(org)
        await session.flush()
        session.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
        session.add(AuditEvent(organization_id=org.id, actor_user_id=user.id, action="organization.created", resource_type="organization", resource_id=org.id))
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "An account with this email already exists") from None
    return AuthOut(access_token=issue_token(user.id), user=UserOut(id=user.id, email=user.email, name=user.name))

@app.post(f"{settings.api_prefix}/auth/login", response_model=AuthOut, tags=["identity"])
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> AuthOut:
    user = await session.scalar(select(User).where(User.email == str(body.email).lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return AuthOut(access_token=issue_token(user.id), user=UserOut(id=user.id, email=user.email, name=user.name))

@app.get(f"{settings.api_prefix}/auth/me", response_model=UserOut, tags=["identity"])
async def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name)

@app.get(f"{settings.api_prefix}/organizations", tags=["organizations"])
async def list_organizations(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict[str, str]]:
    rows = await session.execute(select(Organization, Membership.role).join(Membership).where(Membership.user_id == user.id))
    return [{"id": org.id, "name": org.name, "role": role} for org, role in rows]

@app.post(f"{settings.api_prefix}/projects", response_model=ProjectOut, status_code=201, tags=["projects"])
async def create_project(body: ProjectCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> Project:
    await require_membership(body.organization_id, user, session, {"owner", "admin", "member"})
    project = Project(organization_id=body.organization_id, name=body.name.strip(), description=body.description, building_type=body.building_type, location=body.location, created_by=user.id)
    session.add(project)
    await session.flush()
    session.add(AuditEvent(organization_id=project.organization_id, actor_user_id=user.id, action="project.created", resource_type="project", resource_id=project.id))
    await session.commit()
    await session.refresh(project)
    return project

@app.get(f"{settings.api_prefix}/projects", response_model=list[ProjectOut], tags=["projects"])
async def list_projects(organization_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[Project]:
    await require_membership(organization_id, user, session)
    result = await session.scalars(select(Project).where(Project.organization_id == organization_id).order_by(Project.updated_at.desc()))
    return list(result.all())

@app.get(f"{settings.api_prefix}/projects/{{project_id}}", response_model=ProjectOut, tags=["projects"])
async def get_project(project_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> Project:
    project = await session.get(Project, project_id)
    if project is None: raise HTTPException(404, "Project not found")
    await require_membership(project.organization_id, user, session)
    return project

@app.patch(f"{settings.api_prefix}/projects/{{project_id}}", response_model=ProjectOut, tags=["projects"])
async def update_project(project_id: str, body: ProjectCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> Project:
    project = await session.get(Project, project_id)
    if project is None: raise HTTPException(404, "Project not found")
    membership = await require_membership(project.organization_id, user, session, {"owner", "admin", "member"})
    if body.organization_id != project.organization_id: raise HTTPException(422, "Project organization cannot be changed")
    if membership.role == "viewer": raise HTTPException(403, "Viewer cannot edit projects")
    project.name, project.description = body.name.strip(), body.description
    project.building_type, project.location = body.building_type, body.location
    project.version += 1
    session.add(AuditEvent(organization_id=project.organization_id, actor_user_id=user.id, action="project.updated", resource_type="project", resource_id=project.id))
    await session.commit()
    await session.refresh(project)
    return project

from app.domains.world_model.routes import router as world_model_router
app.include_router(world_model_router, prefix=settings.api_prefix)

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

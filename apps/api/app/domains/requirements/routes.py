from fastapi import APIRouter, Depends
from app.dependencies import current_user
from app.db.models import User
from app.domains.requirements.schemas import RequirementAnalysisRequest, RequirementAnalysisResponse
from app.domains.requirements.service import analyze_brief
from app.domains.brief.routes import router as brief_router
from app.domains.requirements.persistence import extract, list_requirements, set_status

router = APIRouter(tags=["requirements"])

@router.post("/requirements/analyze", response_model=RequirementAnalysisResponse)
async def analyze_requirements(body: RequirementAnalysisRequest, _user: User = Depends(current_user)) -> RequirementAnalysisResponse:
    requirements, missing, issues = analyze_brief(body.brief)
    return RequirementAnalysisResponse(requirements=requirements, missing_information=missing, issues=issues)

@router.post("/projects/{project_id}/versions/{version_ref}/requirements/extract")
async def extract_requirements(project_id: str, version_ref: str, user: User = Depends(current_user), session=Depends(__import__('app.db.session', fromlist=['get_session']).get_session)):
    return await extract(session, project_id, version_ref, user)

@router.get("/projects/{project_id}/versions/{version_ref}/requirements")
async def get_requirements(project_id: str, version_ref: str, user: User = Depends(current_user), session=Depends(__import__('app.db.session', fromlist=['get_session']).get_session)):
    return await list_requirements(session, project_id, version_ref, user)

@router.post("/projects/{project_id}/versions/{version_ref}/requirements/{requirement_id}/confirm")
async def confirm_requirement(project_id: str, version_ref: str, requirement_id: str, user: User = Depends(current_user), session=Depends(__import__('app.db.session', fromlist=['get_session']).get_session)):
    return await set_status(session, project_id, version_ref, requirement_id, "CONFIRMED", user)

@router.post("/projects/{project_id}/versions/{version_ref}/requirements/{requirement_id}/reject")
async def reject_requirement(project_id: str, version_ref: str, requirement_id: str, user: User = Depends(current_user), session=Depends(__import__('app.db.session', fromlist=['get_session']).get_session)):
    return await set_status(session, project_id, version_ref, requirement_id, "REJECTED", user)

router.include_router(brief_router)

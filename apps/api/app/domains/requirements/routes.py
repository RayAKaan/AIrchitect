from fastapi import APIRouter, Depends
from app.dependencies import current_user
from app.db.models import User
from app.domains.requirements.schemas import RequirementAnalysisRequest, RequirementAnalysisResponse
from app.domains.requirements.service import analyze_brief

router = APIRouter(tags=["requirements"])

@router.post("/requirements/analyze", response_model=RequirementAnalysisResponse)
async def analyze_requirements(body: RequirementAnalysisRequest, _user: User = Depends(current_user)) -> RequirementAnalysisResponse:
    requirements, missing, issues = analyze_brief(body.brief)
    return RequirementAnalysisResponse(requirements=requirements, missing_information=missing, issues=issues)

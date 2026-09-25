from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import read_token
from app.db.models import Membership, User
from app.db.session import get_session

bearer = HTTPBearer(auto_error=False)

async def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), session: AsyncSession = Depends(get_session)) -> User:
    if credentials is None: raise HTTPException(401, "Authentication required")
    user_id = read_token(credentials.credentials)
    user = await session.get(User, user_id)
    if user is None: raise HTTPException(401, "Session user no longer exists")
    return user

async def require_membership(org_id: str, user: User, session: AsyncSession, roles: set[str] | None = None) -> Membership:
    membership = await session.scalar(select(Membership).where(Membership.organization_id == org_id, Membership.user_id == user.id))
    if membership is None: raise HTTPException(404, "Organization not found")
    if roles and membership.role not in roles: raise HTTPException(403, "Insufficient organization role")
    return membership

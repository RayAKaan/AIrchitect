from datetime import timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import read_token_claims
from app.db.models import AuthSession, Membership, User, now
from app.db.session import get_session

bearer = HTTPBearer(auto_error=False)


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(401, "Authentication required")
    claims = read_token_claims(credentials.credentials)
    auth_session = await session.get(AuthSession, claims["sid"])
    if auth_session is None or auth_session.user_id != claims["sub"] or auth_session.revoked_at is not None:
        raise HTTPException(401, "Session is no longer active")
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now():
        raise HTTPException(401, "Session is no longer active")
    user = await session.get(User, claims["sub"])
    if user is None:
        raise HTTPException(401, "Session user no longer exists")
    return user


async def require_membership(
    org_id: str,
    user: User,
    session: AsyncSession,
    roles: set[str] | None = None,
) -> Membership:
    membership = await session.scalar(
        select(Membership).where(Membership.organization_id == org_id, Membership.user_id == user.id)
    )
    if membership is None:
        raise HTTPException(404, "Organization not found")
    if roles and membership.role not in roles:
        raise HTTPException(403, "Insufficient organization role")
    return membership

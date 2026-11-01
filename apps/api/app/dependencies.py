from datetime import timezone
import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import read_token_claims
from app.db.models import AuthSession, Membership, User, now
from app.db.session import get_session

bearer = HTTPBearer(auto_error=False)
ACCESS_COOKIE_NAME = "airchitect_session"
CSRF_COOKIE_NAME = "airchitect_csrf"


def validate_cookie_csrf(request: Request) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "")
    header_token = request.headers.get("X-CSRF-Token", "")
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(403, "CSRF validation failed")


async def current_session_claims(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if credentials is not None:
        token = credentials.credentials
    else:
        token = request.cookies.get(ACCESS_COOKIE_NAME, "")
        if not token:
            raise HTTPException(401, "Authentication required")
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            validate_cookie_csrf(request)
    return read_token_claims(token)


async def current_user(
    claims: dict = Depends(current_session_claims),
    session: AsyncSession = Depends(get_session),
) -> User:
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

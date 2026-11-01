from __future__ import annotations

import secrets

from fastapi import Response

from app.core.config import settings

ACCESS_COOKIE_NAME = "airchitect_session"
REFRESH_COOKIE_NAME = "airchitect_refresh"
CSRF_COOKIE_NAME = "airchitect_csrf"
ACCESS_TOKEN_TTL_SECONDS = 24 * 60 * 60
REFRESH_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60


def _secure_cookie() -> bool:
    return settings.app_env.strip().lower() not in {"local", "test"}


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    secure = _secure_cookie()
    response.set_cookie(ACCESS_COOKIE_NAME, access_token, max_age=ACCESS_TOKEN_TTL_SECONDS,
                        httponly=True, secure=secure, samesite="lax", path="/")
    response.set_cookie(REFRESH_COOKIE_NAME, refresh_token, max_age=REFRESH_TOKEN_TTL_SECONDS,
                        httponly=True, secure=secure, samesite="lax", path="/")
    response.set_cookie(CSRF_COOKIE_NAME, secrets.token_urlsafe(32), max_age=REFRESH_TOKEN_TTL_SECONDS,
                        httponly=False, secure=secure, samesite="lax", path="/")


def clear_auth_cookies(response: Response) -> None:
    secure = _secure_cookie()
    for name in (ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, CSRF_COOKIE_NAME):
        response.delete_cookie(name, path="/", secure=secure, samesite="lax")

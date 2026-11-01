from __future__ import annotations

import uuid

import httpx
import pytest


@pytest.mark.asyncio
async def test_registration_issues_http_only_cookies_and_cookie_auth_requires_csrf(api: httpx.AsyncClient) -> None:
    email = "cookie-" + uuid.uuid4().hex + "@example.com"
    registered = await api.post("/api/v1/auth/register", json={
        "email": email, "name": "Cookie User", "password": "a-very-secure-password", "organization_name": "Cookie Org"
    })
    assert registered.status_code == 201, registered.text
    assert registered.cookies.get("airchitect_session")
    assert registered.cookies.get("airchitect_refresh")
    assert registered.cookies.get("airchitect_csrf")
    set_cookie = registered.headers.get_list("set-cookie")
    assert any("airchitect_session=" in value and "HttpOnly" in value for value in set_cookie)
    assert any("airchitect_refresh=" in value and "HttpOnly" in value for value in set_cookie)
    assert any("airchitect_csrf=" in value and "HttpOnly" not in value for value in set_cookie)
    me = await api.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["email"] == email
    org = (await api.get("/api/v1/organizations")).json()[0]
    denied = await api.post("/api/v1/projects", json={"organization_id": org["id"], "name": "CSRF blocked"})
    assert denied.status_code == 403
    csrf = api.cookies.get("airchitect_csrf")
    allowed = await api.post("/api/v1/projects", headers={"X-CSRF-Token": csrf}, json={
        "organization_id": org["id"], "name": "CSRF protected project"
    })
    assert allowed.status_code == 201, allowed.text


@pytest.mark.asyncio
async def test_refresh_rotates_refresh_token_and_logout_clears_cookies(api: httpx.AsyncClient) -> None:
    email = "refresh-" + uuid.uuid4().hex + "@example.com"
    registered = await api.post("/api/v1/auth/register", json={
        "email": email, "name": "Refresh User", "password": "a-very-secure-password", "organization_name": "Refresh Org"
    })
    assert registered.status_code == 201
    original_refresh = registered.json()["refresh_token"]
    csrf = api.cookies.get("airchitect_csrf")
    refreshed = await api.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf}, json={})
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["access_token"] != registered.json()["access_token"]
    assert refreshed.json()["refresh_token"] != original_refresh
    replay = await api.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert replay.status_code == 401
    csrf = api.cookies.get("airchitect_csrf")
    logout = await api.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout.status_code == 200
    assert (await api.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_body_supports_non_browser_clients(api: httpx.AsyncClient) -> None:
    email = "refresh-api-" + uuid.uuid4().hex + "@example.com"
    registered = await api.post("/api/v1/auth/register", json={
        "email": email, "name": "API Refresh", "password": "a-very-secure-password", "organization_name": "API Org"
    })
    token = registered.json()["refresh_token"]
    refreshed = await api.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != token

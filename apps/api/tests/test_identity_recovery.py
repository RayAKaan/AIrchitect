from __future__ import annotations

import uuid

import httpx
import pytest

from app.core.config import settings


def configure_mail(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_sender", "noreply@example.test")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_username", "")
    monkeypatch.setattr(settings, "smtp_password", "")
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(settings, "smtp_ssl", False)
    sent: list[tuple[str, str, str]] = []
    import app.main as main
    monkeypatch.setattr(main, "send_email", lambda recipient, subject, body: sent.append((recipient, subject, body)))
    return sent


@pytest.mark.asyncio
async def test_email_verification_is_single_use_and_required_before_login(api: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    sent = configure_mail(monkeypatch)
    email = "verify-" + uuid.uuid4().hex + "@example.com"
    registered = await api.post("/api/v1/auth/register", json={
        "email": email, "name": "Verify User", "password": "a-very-secure-password", "organization_name": "Verify Org"
    })
    assert registered.status_code == 201, registered.text
    assert registered.json()["verification_required"] is True
    assert registered.json()["access_token"] == ""
    token = registered.json()["debug_token"]
    assert token and len(sent) == 1 and sent[0][0] == email
    denied = await api.post("/api/v1/auth/login", json={"email": email, "password": "a-very-secure-password"})
    assert denied.status_code == 403
    verified = await api.post("/api/v1/auth/verify-email", json={"token": token})
    assert verified.status_code == 200 and verified.json() == {"verified": True}
    replay = await api.post("/api/v1/auth/verify-email", json={"token": token})
    assert replay.status_code == 400
    login = await api.post("/api/v1/auth/login", json={"email": email, "password": "a-very-secure-password"})
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_is_generic_single_use_and_revokes_sessions(api: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    sent = configure_mail(monkeypatch)
    email = "reset-" + uuid.uuid4().hex + "@example.com"
    registered = await api.post("/api/v1/auth/register", json={
        "email": email, "name": "Reset User", "password": "a-very-secure-password", "organization_name": "Reset Org"
    })
    assert registered.status_code == 201
    headers = {"Authorization": "Bearer " + registered.json()["access_token"]}
    unknown = await api.post("/api/v1/auth/forgot-password", json={"email": "unknown@example.com"})
    requested = await api.post("/api/v1/auth/forgot-password", json={"email": email})
    assert unknown.status_code == requested.status_code == 200
    assert unknown.json()["message"] == requested.json()["message"]
    token = requested.json()["debug_token"]
    assert token and len(sent) == 1
    reset = await api.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "a-different-secure-password"})
    assert reset.status_code == 200 and reset.json() == {"password_reset": True}
    replay = await api.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "another-secure-password"})
    assert replay.status_code == 400
    assert (await api.get("/api/v1/auth/me", headers=headers)).status_code == 401
    old_login = await api.post("/api/v1/auth/login", json={"email": email, "password": "a-very-secure-password"})
    new_login = await api.post("/api/v1/auth/login", json={"email": email, "password": "a-different-secure-password"})
    assert old_login.status_code == 401 and new_login.status_code == 200

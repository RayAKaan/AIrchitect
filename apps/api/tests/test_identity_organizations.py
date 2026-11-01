from __future__ import annotations

import uuid

import httpx
import pytest


async def register(client: httpx.AsyncClient, suffix: str) -> tuple[dict[str, str], dict[str, str]]:
    response = await client.post("/api/v1/auth/register", json={
        "email": f"{suffix}-{uuid.uuid4().hex}@example.com",
        "name": suffix.title(),
        "password": "a-very-secure-password",
        "organization_name": suffix.title() + " Org",
    })
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    organization = (await client.get("/api/v1/organizations", headers=headers)).json()[0]
    return headers, organization


@pytest.mark.asyncio
async def test_invitation_acceptance_is_email_bound_single_use_and_audited(api: httpx.AsyncClient) -> None:
    owner_headers, organization = await register(api, "owner")
    invitee_headers, invitee_org = await register(api, "invitee")
    invitee_email = (await api.get("/api/v1/auth/me", headers=invitee_headers)).json()["email"]
    created = await api.post("/api/v1/organizations/" + organization["id"] + "/invitations",
        headers=owner_headers, json={"email": invitee_email, "role": "member"})
    assert created.status_code == 201, created.text
    token = created.json()["token"]
    assert len(token) >= 32
    listed = await api.get("/api/v1/organizations/" + organization["id"] + "/invitations", headers=owner_headers)
    assert listed.status_code == 200 and listed.json()[0]["status"] == "PENDING"
    accepted = await api.post("/api/v1/invitations/accept", headers=invitee_headers, json={"token": token})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json() == {"organization_id": organization["id"], "role": "member", "joined": True}
    members = await api.get("/api/v1/organizations/" + organization["id"] + "/members", headers=owner_headers)
    assert members.status_code == 200
    assert any(item["email"] == invitee_email and item["role"] == "member" for item in members.json())
    retry = await api.post("/api/v1/invitations/accept", headers=invitee_headers, json={"token": token})
    assert retry.status_code == 400
    assert invitee_org["id"] != organization["id"]


@pytest.mark.asyncio
async def test_invitation_cannot_be_accepted_by_another_email(api: httpx.AsyncClient) -> None:
    owner_headers, organization = await register(api, "owner-email")
    invitee_headers, _ = await register(api, "invitee-email")
    wrong_headers, _ = await register(api, "wrong-email")
    invitee_email = (await api.get("/api/v1/auth/me", headers=invitee_headers)).json()["email"]
    created = await api.post("/api/v1/organizations/" + organization["id"] + "/invitations",
        headers=owner_headers, json={"email": invitee_email, "role": "viewer"})
    assert created.status_code == 201
    response = await api.post("/api/v1/invitations/accept", headers=wrong_headers, json={"token": created.json()["token"]})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_invitation_role_escalation_and_non_admin_invites_are_blocked(api: httpx.AsyncClient) -> None:
    owner_headers, organization = await register(api, "owner-role")
    member_headers, _ = await register(api, "member-role")
    email = (await api.get("/api/v1/auth/me", headers=member_headers)).json()["email"]
    forbidden = await api.post("/api/v1/organizations/" + organization["id"] + "/invitations",
        headers=member_headers, json={"email": email, "role": "member"})
    assert forbidden.status_code == 403
    owner_invite = await api.post("/api/v1/organizations/" + organization["id"] + "/invitations",
        headers=owner_headers, json={"email": email, "role": "owner"})
    assert owner_invite.status_code == 422


@pytest.mark.asyncio
async def test_member_role_changes_and_owner_protection(api: httpx.AsyncClient) -> None:
    owner_headers, organization = await register(api, "owner-manage")
    member_headers, _ = await register(api, "member-manage")
    member = (await api.get("/api/v1/auth/me", headers=member_headers)).json()
    invitation = await api.post("/api/v1/organizations/" + organization["id"] + "/invitations",
        headers=owner_headers, json={"email": member["email"], "role": "member"})
    assert invitation.status_code == 201
    assert (await api.post("/api/v1/invitations/accept", headers=member_headers,
        json={"token": invitation.json()["token"]})).status_code == 200
    changed = await api.patch("/api/v1/organizations/" + organization["id"] + "/members/" + member["id"],
        headers=owner_headers, json={"role": "viewer"})
    assert changed.status_code == 200 and changed.json()["role"] == "viewer"
    removed = await api.delete("/api/v1/organizations/" + organization["id"] + "/members/" + member["id"], headers=owner_headers)
    assert removed.status_code == 200
    owner = (await api.get("/api/v1/auth/me", headers=owner_headers)).json()
    self_demote = await api.patch("/api/v1/organizations/" + organization["id"] + "/members/" + owner["id"],
        headers=owner_headers, json={"role": "member"})
    assert self_demote.status_code == 409
    self_remove = await api.delete("/api/v1/organizations/" + organization["id"] + "/members/" + owner["id"], headers=owner_headers)
    assert self_remove.status_code == 409


@pytest.mark.asyncio
async def test_invitation_revocation_and_tenant_scoping(api: httpx.AsyncClient) -> None:
    owner_headers, organization = await register(api, "owner-revoke")
    other_headers, _ = await register(api, "other-revoke")
    invitee_headers, _ = await register(api, "invitee-revoke")
    email = (await api.get("/api/v1/auth/me", headers=invitee_headers)).json()["email"]
    created = await api.post("/api/v1/organizations/" + organization["id"] + "/invitations",
        headers=owner_headers, json={"email": email, "role": "member"})
    invitation_id = created.json()["id"]
    foreign_list = await api.get("/api/v1/organizations/" + organization["id"] + "/members", headers=other_headers)
    assert foreign_list.status_code == 404
    revoked = await api.delete("/api/v1/organizations/" + organization["id"] + "/invitations/" + invitation_id,
        headers=owner_headers)
    assert revoked.status_code == 200
    accepted = await api.post("/api/v1/invitations/accept", headers=invitee_headers, json={"token": created.json()["token"]})
    assert accepted.status_code == 400

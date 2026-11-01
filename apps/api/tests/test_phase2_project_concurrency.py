from __future__ import annotations

import uuid

import httpx
import pytest


async def register(client: httpx.AsyncClient, suffix: str) -> tuple[dict[str, str], dict[str, str]]:
    response = await client.post("/api/v1/auth/register", json={
        "email": suffix + "-" + uuid.uuid4().hex + "@example.com",
        "name": suffix.title(),
        "password": "a-very-secure-password",
        "organization_name": suffix.title() + " Org",
    })
    assert response.status_code == 201, response.text
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    organization = (await client.get("/api/v1/organizations", headers=headers)).json()[0]
    return headers, organization


async def create_project(client: httpx.AsyncClient, headers: dict[str, str], organization: dict[str, str]) -> httpx.Response:
    return await client.post("/api/v1/projects", headers=headers, json={
        "organization_id": organization["id"], "name": "Versioned Project", "description": "Initial"
    })


@pytest.mark.asyncio
async def test_project_updates_require_if_match_and_reject_stale_versions(api: httpx.AsyncClient) -> None:
    headers, organization = await register(api, "project-etag")
    created = await create_project(api, headers, organization)
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["version"] == 1
    assert created.headers["etag"] == '"1"'
    current = await api.get("/api/v1/projects/" + project["id"], headers=headers)
    assert current.headers["etag"] == '"1"'
    body = {"organization_id": organization["id"], "name": "Updated", "description": "First edit"}
    missing = await api.patch("/api/v1/projects/" + project["id"], headers=headers, json=body)
    assert missing.status_code == 428
    updated = await api.patch("/api/v1/projects/" + project["id"], headers={**headers, "If-Match": '"1"'}, json=body)
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2 and updated.headers["etag"] == '"2"'
    stale = await api.patch("/api/v1/projects/" + project["id"], headers={**headers, "If-Match": '"1"'}, json=body)
    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "PRECONDITION_FAILED"
    invalid = await api.patch("/api/v1/projects/" + project["id"], headers={**headers, "If-Match": "not-a-version"}, json=body)
    assert invalid.status_code == 400
    weak = await api.patch("/api/v1/projects/" + project["id"], headers={**headers, "If-Match": 'W/"2"'}, json=body)
    assert weak.status_code == 400
    wildcard = await api.patch("/api/v1/projects/" + project["id"], headers={**headers, "If-Match": "*"}, json=body)
    assert wildcard.status_code == 400


@pytest.mark.asyncio
async def test_project_updates_remain_tenant_scoped_and_role_checked(api: httpx.AsyncClient) -> None:
    owner_headers, organization = await register(api, "project-owner")
    other_headers, _ = await register(api, "project-other")
    created = await create_project(api, owner_headers, organization)
    project_id = created.json()["id"]
    body = {"organization_id": organization["id"], "name": "Foreign edit", "description": "No access"}
    foreign_get = await api.get("/api/v1/projects/" + project_id, headers=other_headers)
    assert foreign_get.status_code == 404
    foreign_list = await api.get("/api/v1/projects", headers=other_headers, params={"organization_id": organization["id"]})
    assert foreign_list.status_code == 404
    foreign_update = await api.patch("/api/v1/projects/" + project_id,
        headers={**other_headers, "If-Match": '"1"'}, json=body)
    assert foreign_update.status_code == 404
    invitee_headers, _ = await register(api, "project-viewer")
    invitee = (await api.get("/api/v1/auth/me", headers=invitee_headers)).json()
    invitation = await api.post("/api/v1/organizations/" + organization["id"] + "/invitations",
        headers=owner_headers, json={"email": invitee["email"], "role": "viewer"})
    assert invitation.status_code == 201
    accepted = await api.post("/api/v1/invitations/accept", headers=invitee_headers, json={"token": invitation.json()["token"]})
    assert accepted.status_code == 200
    viewer_update = await api.patch("/api/v1/projects/" + project_id,
        headers={**invitee_headers, "If-Match": '"1"'}, json=body)
    assert viewer_update.status_code == 403

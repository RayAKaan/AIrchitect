from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.session import get_session
from app.main import app


@pytest.fixture
async def identity_api():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


async def create_identity(client: httpx.AsyncClient, suffix: str) -> tuple[dict[str, str], str]:
    email = f'{suffix}-{uuid.uuid4().hex}@example.com'
    response = await client.post('/api/v1/auth/register', json={
        'email': email, 'name': 'Identity Test', 'password': 'a-very-secure-password', 'organization_name': 'Identity Org'
    })
    assert response.status_code == 201, response.text
    token = response.json()['access_token']
    return {'Authorization': f'Bearer {token}'}, token


@pytest.mark.asyncio
async def test_logout_revokes_only_the_current_session(identity_api: httpx.AsyncClient) -> None:
    headers, _ = await create_identity(identity_api, 'logout')
    assert (await identity_api.get('/api/v1/auth/me', headers=headers)).status_code == 200
    response = await identity_api.post('/api/v1/auth/logout', headers=headers)
    assert response.status_code == 200 and response.json() == {'revoked': True}
    assert (await identity_api.get('/api/v1/auth/me', headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_logout_all_revokes_every_session_for_the_user(identity_api: httpx.AsyncClient) -> None:
    headers, _ = await create_identity(identity_api, 'logout-all')
    me = (await identity_api.get('/api/v1/auth/me', headers=headers)).json()
    login = await identity_api.post('/api/v1/auth/login', json={'email': me['email'], 'password': 'a-very-secure-password'})
    assert login.status_code == 200
    second_headers = {'Authorization': f"Bearer {login.json()['access_token']}"}
    result = await identity_api.post('/api/v1/auth/logout-all', headers=headers)
    assert result.status_code == 200 and result.json()['revoked_sessions'] == 2
    assert (await identity_api.get('/api/v1/auth/me', headers=headers)).status_code == 401
    assert (await identity_api.get('/api/v1/auth/me', headers=second_headers)).status_code == 401


@pytest.mark.asyncio
async def test_user_cannot_revoke_another_users_session(identity_api: httpx.AsyncClient) -> None:
    _, token_a = await create_identity(identity_api, 'owner-a')
    headers_b, _ = await create_identity(identity_api, 'owner-b')
    headers_a = {'Authorization': f'Bearer {token_a}'}
    sessions = await identity_api.get('/api/v1/auth/sessions', headers=headers_a)
    assert sessions.status_code == 200
    session_id = sessions.json()[0]['id']
    response = await identity_api.delete('/api/v1/auth/sessions/' + session_id, headers=headers_b)
    assert response.status_code == 404
    assert (await identity_api.get('/api/v1/auth/me', headers=headers_a)).status_code == 200


@pytest.mark.asyncio
async def test_session_listing_marks_the_calling_session(identity_api: httpx.AsyncClient) -> None:
    headers, _ = await create_identity(identity_api, 'list-sessions')
    response = await identity_api.get('/api/v1/auth/sessions', headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]['current'] is True
    assert response.json()[0]['revoked_at'] is None

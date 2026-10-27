import pytest
from mcp import Client

from app.core.security import issue_token
from app.domains.ai.mcp_server import SessionTokenVerifier, mcp


@pytest.mark.asyncio
async def test_mcp_catalog_exposes_safe_agent_tools() -> None:
    async with Client(mcp) as client:
        result = await client.list_tools()

    names = {tool.name for tool in result.tools}
    assert names == {"get_project_context", "preview_intent", "preview_change"}


@pytest.mark.asyncio
async def test_mcp_token_verifier_accepts_ai_rchitect_session_token() -> None:
    verifier = SessionTokenVerifier()
    token = issue_token("user-123")

    access = await verifier.verify_token(token)

    assert access is not None
    assert access.client_id == "user-123"
    assert "airchitect:read" in access.scopes

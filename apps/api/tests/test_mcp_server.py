import pytest
from mcp import Client

from app.core.security import issue_token
from app.domains.ai.mcp_server import SessionTokenVerifier, mcp


@pytest.mark.asyncio
async def test_mcp_catalog_exposes_scoped_read_and_preview_tools() -> None:
    async with Client(mcp) as client:
        result = await client.list_tools()

    names = {tool.name for tool in result.tools}
    assert names == {
        "get_project_context",
        "get_site_context",
        "list_design_alternatives",
        "list_project_artifacts",
        "preview_intent",
        "preview_change",
    }


@pytest.mark.asyncio
async def test_mcp_token_verifier_accepts_ai_rchitect_session_token() -> None:
    verifier = SessionTokenVerifier()
    token = issue_token("user-123")

    access = await verifier.verify_token(token)

    assert access is not None
    assert access.client_id == "user-123"
    assert "airchitect:read" in access.scopes


@pytest.mark.asyncio
async def test_mcp_context_tools_are_documented_as_non_mutating() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    descriptions = {tool.name: tool.description or "" for tool in tools.tools}
    assert "without selecting or changing them" in descriptions["list_design_alternatives"]
    assert "freshness status and dependency lineage" in descriptions["list_project_artifacts"]
    assert "latest canonical site revision" in descriptions["get_site_context"]

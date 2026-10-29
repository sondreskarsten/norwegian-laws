import json

import pytest

from norwegian_laws_mcp.server import build_server

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="module")
def server(service):
    return build_server(service)


async def test_tools_are_registered(server):
    tools = await server.list_tools()
    names = {t.name for t in tools}
    assert {
        "laws_search_documents", "laws_get_document", "laws_search_text", "laws_find_definition",
        "laws_recent_changes", "laws_document_history", "laws_diff_document", "laws_blame_section",
        "laws_amendment_records", "laws_related_documents", "laws_repo_status", "laws_update_repo",
    } <= names
    for t in tools:
        assert t.description
        assert t.annotations is not None


async def test_call_tools(server):
    res = await server.call_tool("laws_find_definition", {"term": "underenheter"})
    assert "Med underenhet menes" in res.content[0].text
    res = await server.call_tool("laws_search_documents", {"query": "asl", "format": "json"})
    assert json.loads(res.content[0].text)[0]["refid"] == "lov/1997-06-13-44"
    res = await server.call_tool("laws_get_document", {"ref": "asl", "section": "§ 1-5 a"})
    assert "elektronisk møte" in res.content[0].text
    res = await server.call_tool("laws_recent_changes", {"since": "2026-02-15"})
    assert "modified" in res.content[0].text
    res = await server.call_tool("laws_get_document", {"ref": "no-such-law"})
    assert res.content[0].text.startswith("Error:")


async def test_stdio_roundtrip(fixture_repo):
    import sys
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "norwegian_laws_mcp.cli", "--repo", str(fixture_repo), "--no-update"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            assert init.server_info.name == "norwegian_laws_mcp"
            tools = await session.list_tools()
            assert any(t.name == "laws_search_text" for t in tools.tools)
            result = await session.call_tool("laws_search_text", {"query": "underenhet", "kind": "lov"})
            assert "lov/2025-06-20-105" in result.content[0].text

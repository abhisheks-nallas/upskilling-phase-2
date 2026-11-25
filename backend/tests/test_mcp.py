import sys
from pathlib import Path

from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from strands.tools.mcp import MCPClient

import main
from test_api import FakeModel, HEADERS, client, parse_sse

SERVER = StdioServerParameters(command=sys.executable, args=[str(Path(main.__file__).parent / "mcp_docs_server.py")])


def test_client_discovers_and_calls_tools_over_mcp():
    with MCPClient(lambda: stdio_client(SERVER)) as mcp_client:
        tools = {t.tool_name: t for t in mcp_client.list_tools_sync()}
        assert set(tools) == {"search_company_docs", "get_access_checklist"}
        result = mcp_client.call_tool_sync("t1", "get_access_checklist", {"role": "qa"})
        assert result["status"] == "success" and "email" in result["content"][0]["text"].lower()


def test_agent_answers_through_the_mcp_tool(monkeypatch):
    monkeypatch.setenv("USE_MCP", "1")
    monkeypatch.setattr(main.Assistant, "init_llm_model", lambda self: FakeModel())
    resp = client.post("/chat/stream", json={"message": "what access does QA need?"}, headers=HEADERS)
    events = parse_sse(resp.text)
    assert events[-1][0] == "done"
    assert "You need:" in "".join(e[1].get("text", "") for e in events)

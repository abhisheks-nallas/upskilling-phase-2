"""MCP server that exposes two Onboarding Buddy tools (Wk 4: MCP integration).

Any MCP client can connect, list the tools and call them. The Strands agent does this when USE_MCP=1 (see main.py).
Run it by hand:  python mcp_docs_server.py   (talks MCP over stdin/stdout)
"""
from mcp.server.mcpserver import MCPServer

import onboarding_tools

server = MCPServer("onboarding-docs")


@server.tool()
def search_company_docs(question:str) -> str:
    """Look up company policies and how things work: leave, working hours, IT setup, expenses and travel, security,
    probation and reviews, learning budget, benefits and payroll, code review and releases, who to contact."""
    return onboarding_tools.search_company_docs(question)


@server.tool()
def get_access_checklist(role:str) -> str:
    """List the accounts and tools a new joiner in this role needs on day one (developer, qa, ba or pm)."""
    return onboarding_tools.get_access_checklist(role)


if __name__ == "__main__":
    server.run()   # stdio, the simplest transport

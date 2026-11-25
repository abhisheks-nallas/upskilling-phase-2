# MCP in Onboarding Buddy (Wk 4 hands-on example)

## What MCP is
The Model Context Protocol is a standard way for an AI agent (the client) to use tools that live in another program (the server).
The server says which tools it has, the client discovers them at runtime, and the agent calls them like its own. The agent code does not need to know how the tool is built.

## What we built
- **Server:** `backend/mcp_docs_server.py` exposes two tools, `search_company_docs` (the RAG v2 search) and `get_access_checklist`. It talks MCP over stdin/stdout.
- **Client:** with `USE_MCP=1`, the Strands agent in `backend/main.py` starts that server and connects with Strands' `MCPClient`. It asks the server for its tool list and gets both tools without us listing them.
- **Off by default.** Without `USE_MCP=1` the same tools are plain Python functions, so the deployed API is unchanged.
- **Tests:** `backend/tests/test_mcp.py` connects a client, checks the discovered tool names, calls a tool, and runs the agent through the MCP tool with a fake model.
- **Live check:** with the real Groq model and `USE_MCP=1`, a leave question and an access question were both answered through the MCP tools, with no error.

## How a client service could expose tools the same way
A team with an internal service (for example a policy lookup or a ticket search) wraps the calls it wants to share in a small MCP server, one function per tool with a clear docstring and typed arguments.
Any agent that speaks MCP can then connect, discover those tools and use them, without a custom integration for each agent.
Points to settle before doing it for real: who may connect (authentication), which tools are read-only, and what data a tool may return.
This note describes the pattern only. No client system or data was used.

## Limits of this example
- One server process is started per request, which reloads the search index each time. Fine for a demo, a shared long-running server is the next step.
- It uses the stdio transport on one machine. A service run by another team would use the HTTP transport.

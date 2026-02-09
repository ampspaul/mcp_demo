from langchain_mcp_adapters.client import MultiServerMCPClient
from shared.settings import settings

_MCP_TOOLS: dict | None = None


async def get_mcp_tool_by_name() -> dict:
    """
    Build MCP client + tools once per process and reuse.
    DO NOT store tool objects in LangGraph state (will be dropped / not serializable).
    """
    global _MCP_TOOLS
    if _MCP_TOOLS is not None:
        return _MCP_TOOLS

    client = MultiServerMCPClient(
        {
            "loa": {
                "url": settings.mcp_sse_url,
                "transport": "sse",
            }
        }
    )
    tools = await client.get_tools()
    tool_by_name = {t.name: t for t in tools}

    # Ensure tools exist
    expected = {"validate_employee", "get_leave_balance","create_loa"}
    missing = expected - set(tool_by_name.keys())
    if missing:
        raise RuntimeError(
            f"Missing MCP tools: {sorted(missing)}. "
            f"Available tools: {sorted(tool_by_name.keys())}"
        )

    _MCP_TOOLS = tool_by_name
    return tool_by_name
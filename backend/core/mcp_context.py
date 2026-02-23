"""ContextVar for MCP user/advertiser context in SSE mode."""
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class MCPUserContext:
    user_id: int
    advertiser_id: int  # Primary advertiser (first one)
    advertiser_ids: list[int] | None = None  # All advertisers
    competitor_ids: list[int] | None = None


mcp_user_context: ContextVar[MCPUserContext | None] = ContextVar(
    "mcp_user_context", default=None
)

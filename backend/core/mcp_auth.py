"""ASGI middleware: validate MCP API key from query params, set context."""
import logging
from urllib.parse import parse_qs

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from core.mcp_context import MCPUserContext, mcp_user_context
from database import SessionLocal, User, UserAdvertiser
from core.permissions import get_advertiser_competitor_ids

logger = logging.getLogger(__name__)

# Cache: api_key -> MCPUserContext (avoids DB lookup on every /messages/ call)
_key_contexts: dict[str, MCPUserContext] = {}


def _resolve_context(api_key: str) -> MCPUserContext | None:
    """Resolve user context from api_key, with cache."""
    if api_key in _key_contexts:
        return _key_contexts[api_key]

    db = SessionLocal()
    try:
        user = db.query(User).filter(
            User.mcp_api_key == api_key,
            User.is_active == True,
        ).first()

        if not user:
            return None

        ua = db.query(UserAdvertiser).filter(
            UserAdvertiser.user_id == user.id,
        ).order_by(UserAdvertiser.id).first()

        if not ua:
            return None

        competitor_ids = get_advertiser_competitor_ids(db, ua.advertiser_id)

        ctx = MCPUserContext(
            user_id=user.id,
            advertiser_id=ua.advertiser_id,
            competitor_ids=competitor_ids,
        )

        # Cache for reuse (limit size)
        _key_contexts[api_key] = ctx
        if len(_key_contexts) > 50:
            oldest = next(iter(_key_contexts))
            del _key_contexts[oldest]

        return ctx
    finally:
        db.close()


# Last authenticated context (set on SSE connect, reused on messages)
_last_context: MCPUserContext | None = None


class MCPAuthMiddleware:
    """Wrap the MCP SSE ASGI app with API key authentication.

    Auth flow:
    1. Client connects to /sse?api_key=pnrm_xxx → validates key, stores context
    2. Client posts to /messages/?session_id=xxx → reuses last authenticated context
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        global _last_context

        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        qs = parse_qs(scope.get("query_string", b"").decode())
        path = scope.get("path", "")
        api_key = (qs.get("api_key") or [None])[0]
        session_id = (qs.get("session_id") or [None])[0]

        # Messages endpoint: reuse last authenticated context
        if "/messages" in path and session_id:
            if _last_context:
                token = mcp_user_context.set(_last_context)
                try:
                    await self.app(scope, receive, send)
                finally:
                    mcp_user_context.reset(token)
            else:
                await self.app(scope, receive, send)
            return

        # SSE endpoint: validate api_key
        if not api_key or not api_key.startswith("pnrm_"):
            response = JSONResponse(
                {"detail": "API key manquante ou invalide"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        ctx = _resolve_context(api_key)
        if not ctx:
            response = JSONResponse(
                {"detail": "API key invalide ou revoquee"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        # Store as last authenticated context
        _last_context = ctx
        logger.info(f"MCP context set for user {ctx.user_id}, advertiser {ctx.advertiser_id}, {len(ctx.competitor_ids)} competitors")

        token = mcp_user_context.set(ctx)
        try:
            await self.app(scope, receive, send)
        finally:
            mcp_user_context.reset(token)

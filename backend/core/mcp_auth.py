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


# Cache: session_id -> api_key (set on SSE connect, reused on messages)
_session_keys: dict[str, str] = {}


class MCPAuthMiddleware:
    """Wrap the MCP SSE ASGI app with API key authentication.

    Auth flow:
    1. Client connects to /sse?api_key=pnrm_xxx → validates key, caches context
    2. Server returns session_id → we cache session_id -> api_key mapping
    3. Client posts to /messages/?session_id=xxx → we look up api_key from cache
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        qs = parse_qs(scope.get("query_string", b"").decode())
        path = scope.get("path", "")
        api_key = (qs.get("api_key") or [None])[0]
        session_id = (qs.get("session_id") or [None])[0]

        # Messages endpoint: restore context from session -> api_key cache
        if "/messages" in path and session_id:
            cached_key = _session_keys.get(session_id)
            if cached_key:
                ctx = _resolve_context(cached_key)
                if ctx:
                    token = mcp_user_context.set(ctx)
                    try:
                        await self.app(scope, receive, send)
                    finally:
                        mcp_user_context.reset(token)
                    return

            # No cached context — still pass through (MCP validates session_id)
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

        # Capture session_id from SSE response to map session -> api_key
        original_send = send

        async def capturing_send(message):
            if message.get("type") == "http.response.body":
                body = message.get("body", b"").decode(errors="ignore")
                if "session_id=" in body:
                    for line in body.split("\n"):
                        if "session_id=" in line:
                            sid_qs = parse_qs(line.split("?", 1)[-1])
                            sid = (sid_qs.get("session_id") or [None])[0]
                            if sid:
                                _session_keys[sid] = api_key
                                logger.info(f"MCP session {sid[:8]}... mapped to user {ctx.user_id}")
                                if len(_session_keys) > 100:
                                    oldest = next(iter(_session_keys))
                                    del _session_keys[oldest]
                                break
            await original_send(message)

        token = mcp_user_context.set(ctx)
        try:
            await self.app(scope, receive, capturing_send)
        finally:
            mcp_user_context.reset(token)

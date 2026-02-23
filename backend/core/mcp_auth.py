"""ASGI middleware: validate MCP API key from query params, set context."""
import logging
from urllib.parse import parse_qs

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from core.mcp_context import MCPUserContext, mcp_user_context
from database import SessionLocal, User, UserAdvertiser
from core.permissions import get_advertiser_competitor_ids

logger = logging.getLogger(__name__)

# Cache: session_id -> MCPUserContext (set on SSE connect, reused on messages)
_session_contexts: dict[str, MCPUserContext] = {}


class MCPAuthMiddleware:
    """Wrap the MCP SSE ASGI app with API key authentication.

    Auth flow:
    1. Client connects to /sse?api_key=pnrm_xxx → validates key, caches context by session_id
    2. Client posts to /messages/?session_id=xxx → reuses cached context (no api_key needed)
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

        # Messages endpoint: session_id is the auth token (random UUID)
        # Auth was already validated on SSE connect. Let the MCP framework
        # validate the session_id internally.
        if "/messages" in path and session_id:
            # Try to restore context from cache, otherwise pass through
            ctx = _session_contexts.get(session_id)
            if ctx:
                token = mcp_user_context.set(ctx)
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

        # Lookup user by MCP API key
        db = SessionLocal()
        try:
            user = db.query(User).filter(
                User.mcp_api_key == api_key,
                User.is_active == True,
            ).first()

            if not user:
                response = JSONResponse(
                    {"detail": "API key invalide ou revoquee"},
                    status_code=401,
                )
                await response(scope, receive, send)
                return

            # Resolve advertiser (first one)
            ua = db.query(UserAdvertiser).filter(
                UserAdvertiser.user_id == user.id,
            ).order_by(UserAdvertiser.id).first()

            if not ua:
                response = JSONResponse(
                    {"detail": "Aucune enseigne configuree pour cet utilisateur"},
                    status_code=403,
                )
                await response(scope, receive, send)
                return

            competitor_ids = get_advertiser_competitor_ids(db, ua.advertiser_id)

            ctx = MCPUserContext(
                user_id=user.id,
                advertiser_id=ua.advertiser_id,
                competitor_ids=competitor_ids,
            )
        finally:
            db.close()

        # Capture session_id from SSE response to cache the context
        original_send = send

        async def capturing_send(message):
            if message.get("type") == "http.response.body":
                body = message.get("body", b"").decode(errors="ignore")
                # SSE sends "data: /messages/?session_id=xxx"
                if "session_id=" in body:
                    for line in body.split("\n"):
                        if "session_id=" in line:
                            sid_qs = parse_qs(line.split("?", 1)[-1])
                            sid = (sid_qs.get("session_id") or [None])[0]
                            if sid:
                                _session_contexts[sid] = ctx
                                logger.info(f"MCP session {sid[:8]}... cached for user {ctx.user_id}")
                                # Limit cache size
                                if len(_session_contexts) > 100:
                                    oldest = next(iter(_session_contexts))
                                    del _session_contexts[oldest]
                                break
            await original_send(message)

        # Set context var and call the app
        token = mcp_user_context.set(ctx)
        try:
            await self.app(scope, receive, capturing_send)
        finally:
            mcp_user_context.reset(token)

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

        # Get ALL advertisers for this user
        user_advs = db.query(UserAdvertiser).filter(
            UserAdvertiser.user_id == user.id,
        ).order_by(UserAdvertiser.id).all()

        if not user_advs:
            return None

        # Aggregate competitors from ALL advertisers
        all_adv_ids = [ua.advertiser_id for ua in user_advs]
        all_comp_ids = set()
        for adv_id in all_adv_ids:
            all_comp_ids.update(get_advertiser_competitor_ids(db, adv_id))

        ctx = MCPUserContext(
            user_id=user.id,
            advertiser_id=user_advs[0].advertiser_id,
            advertiser_ids=all_adv_ids,
            competitor_ids=list(all_comp_ids),
        )
        logger.info(f"MCP context resolved: user={user.id}, advertisers={all_adv_ids}, competitors={list(all_comp_ids)}")

        # Cache for reuse (limit size)
        _key_contexts[api_key] = ctx
        if len(_key_contexts) > 50:
            oldest = next(iter(_key_contexts))
            del _key_contexts[oldest]

        return ctx
    finally:
        db.close()


# Session-scoped contexts (keyed by session_id, not a single global)
_session_contexts: dict[str, MCPUserContext] = {}


class MCPAuthMiddleware:
    """Wrap the MCP SSE ASGI app with API key authentication.

    Auth flow:
    1. Client connects to /sse?api_key=pnrm_xxx → validates key, stores context by session
    2. Client posts to /messages/?session_id=xxx → looks up context for that session
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

        # Messages endpoint: look up context by session_id
        if "/messages" in path and session_id:
            ctx = _session_contexts.get(session_id)
            if ctx:
                token = mcp_user_context.set(ctx)
                try:
                    await self.app(scope, receive, send)
                finally:
                    mcp_user_context.reset(token)
            else:
                # No context for this session — reject
                response = JSONResponse(
                    {"detail": "Session inconnue, reconnectez-vous via /sse"},
                    status_code=401,
                )
                await response(scope, receive, send)
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

        # Store context keyed by session_id (extracted from SSE response later)
        # For SSE connect, use api_key as temporary session key
        temp_session_key = api_key
        if session_id:
            temp_session_key = session_id
        _session_contexts[temp_session_key] = ctx

        # Evict old sessions (limit to 100)
        while len(_session_contexts) > 100:
            oldest = next(iter(_session_contexts))
            del _session_contexts[oldest]

        logger.info(f"MCP context set for user {ctx.user_id}, advertiser {ctx.advertiser_id}, {len(ctx.competitor_ids)} competitors")

        token = mcp_user_context.set(ctx)
        try:
            await self.app(scope, receive, send)
        finally:
            mcp_user_context.reset(token)

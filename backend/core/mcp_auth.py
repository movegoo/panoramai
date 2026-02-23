"""ASGI middleware: validate MCP API key from query params, set context."""
import logging
from urllib.parse import parse_qs, urlparse

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from core.mcp_context import MCPUserContext, mcp_user_context
from database import SessionLocal, User, UserAdvertiser
from core.permissions import get_advertiser_competitor_ids

logger = logging.getLogger(__name__)


class MCPAuthMiddleware:
    """Wrap the MCP SSE ASGI app with API key authentication."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Extract api_key from query string
        qs = parse_qs(scope.get("query_string", b"").decode())
        api_key = (qs.get("api_key") or [None])[0]

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

        # Set context var and call the app
        token = mcp_user_context.set(ctx)
        try:
            await self.app(scope, receive, send)
        finally:
            mcp_user_context.reset(token)

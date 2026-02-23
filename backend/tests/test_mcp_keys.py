"""Tests for MCP API key management and auth middleware."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from starlette.testclient import TestClient
from fastapi import FastAPI
from fastapi.testclient import TestClient as FastAPITestClient

from routers.mcp_keys import router, MCP_BASE_URL
from core.mcp_context import MCPUserContext, mcp_user_context


# ─── Fixtures ─────────────────────────────────────────────────────

def make_user(mcp_api_key=None, user_id=1):
    """Create a mock user."""
    user = MagicMock()
    user.id = user_id
    user.email = "test@example.com"
    user.mcp_api_key = mcp_api_key
    user.is_active = True
    return user


def make_app():
    """Create a test FastAPI app with MCP router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/mcp")
    return app


# ─── Key Generation ──────────────────────────────────────────────

def test_generate_key():
    """Test MCP key generation returns a pnrm_ prefixed key and is verified."""
    app = make_app()
    user = make_user()
    db = MagicMock()

    # Mock SessionLocal for verification query
    mock_verify_db = MagicMock()
    mock_verify_db.query.return_value.filter.return_value.first.return_value = user

    from core.auth import get_current_user
    from database import get_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    with patch("routers.mcp_keys.SessionLocal", return_value=mock_verify_db):
        client = FastAPITestClient(app)
        resp = client.post("/api/mcp/keys/generate")

    assert resp.status_code == 200
    data = resp.json()
    assert "api_key" in data
    assert data["api_key"].startswith("pnrm_")
    assert len(data["api_key"]) == 37  # pnrm_ + 32 hex chars
    assert data["verified"] is True
    # ORM assignment should have been made
    assert user.mcp_api_key == data["api_key"]
    db.commit.assert_called()
    db.refresh.assert_called_with(user)


def test_generate_key_fails_verification():
    """Test that generate returns 500 if key not found after commit."""
    app = make_app()
    user = make_user()
    db = MagicMock()

    # Mock SessionLocal verification to return None (key not found)
    mock_verify_db = MagicMock()
    mock_verify_db.query.return_value.filter.return_value.first.return_value = None

    from core.auth import get_current_user
    from database import get_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    with patch("routers.mcp_keys.SessionLocal", return_value=mock_verify_db):
        client = FastAPITestClient(app)
        resp = client.post("/api/mcp/keys/generate")

    assert resp.status_code == 500
    assert "persistee" in resp.json()["detail"]


def test_generate_key_format():
    """Verify key format: pnrm_ prefix + 32 hex characters."""
    import secrets
    key = f"pnrm_{secrets.token_hex(16)}"
    assert key.startswith("pnrm_")
    assert len(key) == 37
    # hex part should be valid hex
    hex_part = key[5:]
    int(hex_part, 16)  # should not raise


# ─── Key Masking ─────────────────────────────────────────────────

def test_get_key_masked():
    """Test that GET /keys returns a properly masked key."""
    key = "pnrm_a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
    user = make_user(mcp_api_key=key)

    app = make_app()
    from core.auth import get_current_user
    from database import get_db
    db = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    client = FastAPITestClient(app)
    resp = client.get("/api/mcp/keys")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_key"] is True
    assert data["api_key_masked"] == "pnrm_a1b2...c3d4"
    assert "..." in data["api_key_masked"]
    # Full key should NOT be in masked version
    assert data["api_key_masked"] != key


def test_get_key_none():
    """Test GET /keys when no key exists."""
    user = make_user(mcp_api_key=None)

    app = make_app()
    from core.auth import get_current_user
    from database import get_db
    db = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    client = FastAPITestClient(app)
    resp = client.get("/api/mcp/keys")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_key"] is False
    assert data["claude_config"] is None


def test_get_key_claude_config():
    """Test that Claude Desktop config is correct."""
    key = "pnrm_testkey1234567890abcdef12345678"
    user = make_user(mcp_api_key=key)

    app = make_app()
    from core.auth import get_current_user
    from database import get_db
    db = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    client = FastAPITestClient(app)
    resp = client.get("/api/mcp/keys")

    data = resp.json()
    config = data["claude_config"]
    assert "mcpServers" in config
    assert "panoramai" in config["mcpServers"]
    server = config["mcpServers"]["panoramai"]
    assert server["command"] == "npx"
    assert "mcp-remote" in server["args"]
    # The SSE URL with api_key should be in args
    sse_url = server["args"][-1]
    assert f"api_key={key}" in sse_url
    assert "/mcp/sse" in sse_url


# ─── Key Revocation ──────────────────────────────────────────────

def test_revoke_key():
    """Test DELETE /keys revokes the key."""
    user = make_user(mcp_api_key="pnrm_torevoke123456789012345678901234")
    db = MagicMock()

    app = make_app()
    from core.auth import get_current_user
    from database import get_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    client = FastAPITestClient(app)
    resp = client.delete("/api/mcp/keys")

    assert resp.status_code == 200
    assert user.mcp_api_key is None
    db.commit.assert_called_once()


# ─── MCPUserContext ──────────────────────────────────────────────

def test_mcp_context_default():
    """Test that mcp_user_context defaults to None."""
    assert mcp_user_context.get(None) is None


def test_mcp_context_set_reset():
    """Test setting and resetting MCP context."""
    ctx = MCPUserContext(user_id=1, advertiser_id=2, competitor_ids=[3, 4, 5])
    token = mcp_user_context.set(ctx)

    current = mcp_user_context.get()
    assert current is not None
    assert current.user_id == 1
    assert current.advertiser_id == 2
    assert current.competitor_ids == [3, 4, 5]

    mcp_user_context.reset(token)
    assert mcp_user_context.get(None) is None


# ─── Auth Middleware ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auth_middleware_missing_key():
    """Test middleware returns 401 when no api_key provided."""
    from core.mcp_auth import MCPAuthMiddleware

    inner_app = AsyncMock()
    middleware = MCPAuthMiddleware(inner_app)

    scope = {
        "type": "http",
        "query_string": b"",
        "method": "GET",
        "path": "/mcp/sse",
        "headers": [],
    }

    sent_responses = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent_responses.append(message)

    await middleware(scope, receive, send)

    # Should have sent a 401 response
    assert any(m.get("status") == 401 for m in sent_responses)
    inner_app.assert_not_called()


@pytest.mark.asyncio
async def test_auth_middleware_invalid_prefix():
    """Test middleware rejects keys without pnrm_ prefix."""
    from core.mcp_auth import MCPAuthMiddleware

    inner_app = AsyncMock()
    middleware = MCPAuthMiddleware(inner_app)

    scope = {
        "type": "http",
        "query_string": b"api_key=invalid_key_here",
        "method": "GET",
        "path": "/mcp/sse",
        "headers": [],
    }

    sent_responses = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent_responses.append(message)

    await middleware(scope, receive, send)

    assert any(m.get("status") == 401 for m in sent_responses)
    inner_app.assert_not_called()


@pytest.mark.asyncio
async def test_auth_middleware_valid_key():
    """Test middleware passes through with valid key and sets context."""
    from core.mcp_auth import MCPAuthMiddleware

    captured_ctx = []

    async def inner_app(scope, receive, send):
        ctx = mcp_user_context.get(None)
        captured_ctx.append(ctx)
        # Send a minimal response
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = MCPAuthMiddleware(inner_app)

    mock_user = MagicMock()
    mock_user.id = 42
    mock_user.is_active = True
    mock_user.mcp_api_key = "pnrm_validkey1234567890abcdef1234"

    mock_ua = MagicMock()
    mock_ua.advertiser_id = 10

    mock_db = MagicMock()
    # User lookup: query().filter().first()
    # UserAdvertiser lookup: query().filter().order_by().all() (returns list)
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_ua]

    scope = {
        "type": "http",
        "query_string": b"api_key=pnrm_validkey1234567890abcdef1234",
        "method": "GET",
        "path": "/mcp/sse",
        "headers": [],
    }

    with patch("core.mcp_auth.SessionLocal", return_value=mock_db):
        with patch("core.mcp_auth.get_advertiser_competitor_ids", return_value=[1, 2, 3]):
            # Clear cache to force DB lookup
            from core.mcp_auth import _key_contexts
            _key_contexts.clear()
            await middleware(scope, lambda: {"type": "http.request", "body": b""}, AsyncMock())

    assert len(captured_ctx) == 1
    ctx = captured_ctx[0]
    assert ctx is not None
    assert ctx.user_id == 42
    assert ctx.advertiser_id == 10
    assert ctx.competitor_ids == [1, 2, 3]

    # Context should be reset after middleware completes
    assert mcp_user_context.get(None) is None

    # Clean up
    _key_contexts.clear()


@pytest.mark.asyncio
async def test_auth_middleware_messages_reuses_last_context():
    """Test that /messages/ endpoint reuses last authenticated context."""
    import core.mcp_auth as mcp_auth_mod
    from core.mcp_auth import MCPAuthMiddleware

    captured_ctx = []

    async def inner_app(scope, receive, send):
        ctx = mcp_user_context.get(None)
        captured_ctx.append(ctx)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = MCPAuthMiddleware(inner_app)

    # Set last context
    test_ctx = MCPUserContext(user_id=42, advertiser_id=10, competitor_ids=[1, 2])
    old_ctx = mcp_auth_mod._last_context
    mcp_auth_mod._last_context = test_ctx

    scope = {
        "type": "http",
        "query_string": b"session_id=test-session-123",
        "method": "POST",
        "path": "/mcp/messages/",
        "headers": [],
    }

    await middleware(scope, AsyncMock(), AsyncMock())

    assert len(captured_ctx) == 1
    assert captured_ctx[0].user_id == 42
    assert captured_ctx[0].advertiser_id == 10

    # Restore
    mcp_auth_mod._last_context = old_ctx


@pytest.mark.asyncio
async def test_auth_middleware_messages_passes_through_without_cache():
    """Test that /messages/ with session_id passes through even without cache."""
    from core.mcp_auth import MCPAuthMiddleware

    called = []

    async def inner_app(scope, receive, send):
        called.append(True)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = MCPAuthMiddleware(inner_app)

    scope = {
        "type": "http",
        "query_string": b"session_id=unknown-session-456",
        "method": "POST",
        "path": "/mcp/messages/",
        "headers": [],
    }

    await middleware(scope, AsyncMock(), AsyncMock())

    # Should pass through to inner app (not 401)
    assert len(called) == 1

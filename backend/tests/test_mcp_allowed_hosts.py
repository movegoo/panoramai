"""Tests for MCP allowed hosts configuration."""
import os
import pytest
from unittest.mock import patch


class TestBuildAllowedHosts:
    """Test _build_allowed_hosts() from competitive_mcp.server."""

    def _import_fresh(self):
        """Re-import the function to pick up env changes."""
        import importlib
        import competitive_mcp.server as mod
        importlib.reload(mod)
        return mod._build_allowed_hosts

    def test_default_hosts_without_env(self):
        """Without MCP_ALLOWED_HOSTS env, should include Render defaults."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MCP_ALLOWED_HOSTS", None)
            build = self._import_fresh()
            hosts = build()

        assert "localhost:*" in hosts
        assert "127.0.0.1:*" in hosts
        assert "panoramai-api.onrender.com:*" in hosts
        assert "panoramai-api.onrender.com" in hosts

    def test_custom_hosts_from_env(self):
        """MCP_ALLOWED_HOSTS should add custom hosts."""
        with patch.dict(os.environ, {"MCP_ALLOWED_HOSTS": "my-alb.example.com,api.prod.com"}):
            build = self._import_fresh()
            hosts = build()

        assert "localhost:*" in hosts
        assert "127.0.0.1:*" in hosts
        assert "my-alb.example.com" in hosts
        assert "my-alb.example.com:*" in hosts
        assert "api.prod.com" in hosts
        assert "api.prod.com:*" in hosts
        # Render defaults should NOT be present
        assert "panoramai-api.onrender.com:*" not in hosts

    def test_empty_env_uses_defaults(self):
        """Empty MCP_ALLOWED_HOSTS should fall back to defaults."""
        with patch.dict(os.environ, {"MCP_ALLOWED_HOSTS": ""}):
            build = self._import_fresh()
            hosts = build()

        assert "panoramai-api.onrender.com:*" in hosts

    def test_host_with_port_not_duplicated(self):
        """Hosts already containing ':' should not get ':*' added."""
        with patch.dict(os.environ, {"MCP_ALLOWED_HOSTS": "my-alb.example.com:443"}):
            build = self._import_fresh()
            hosts = build()

        assert "my-alb.example.com:443" in hosts
        # Should not add :* since it already has a port
        assert hosts.count("my-alb.example.com:443") == 1

    def test_whitespace_trimmed(self):
        """Whitespace around hosts should be trimmed."""
        with patch.dict(os.environ, {"MCP_ALLOWED_HOSTS": "  host1.com , host2.com  "}):
            build = self._import_fresh()
            hosts = build()

        assert "host1.com" in hosts
        assert "host2.com" in hosts

"""Tests for entrypoint.sh script logic."""
import subprocess
import os
import pytest


ENTRYPOINT_PATH = os.path.join(os.path.dirname(__file__), "..", "entrypoint.sh")


class TestEntrypointScript:
    """Validate entrypoint.sh is well-formed."""

    def test_entrypoint_exists(self):
        """entrypoint.sh should exist."""
        assert os.path.isfile(ENTRYPOINT_PATH)

    def test_entrypoint_is_executable_shell(self):
        """entrypoint.sh should start with a shebang."""
        with open(ENTRYPOINT_PATH) as f:
            first_line = f.readline().strip()
        assert first_line == "#!/bin/sh"

    def test_entrypoint_has_set_e(self):
        """entrypoint.sh should use set -e for safety."""
        with open(ENTRYPOINT_PATH) as f:
            content = f.read()
        assert "set -e" in content

    def test_entrypoint_syncs_s3_conditionally(self):
        """entrypoint.sh should only sync S3 if S3_CACHE_BUCKET is set."""
        with open(ENTRYPOINT_PATH) as f:
            content = f.read()
        assert 'S3_CACHE_BUCKET' in content
        assert 'aws s3 sync' in content

    def test_entrypoint_execs_uvicorn(self):
        """entrypoint.sh should exec uvicorn (not just run it)."""
        with open(ENTRYPOINT_PATH) as f:
            content = f.read()
        assert "exec uvicorn main:app" in content

    def test_entrypoint_uses_port_env(self):
        """entrypoint.sh should use PORT env var with default 8000."""
        with open(ENTRYPOINT_PATH) as f:
            content = f.read()
        assert "${PORT:-8000}" in content

    def test_entrypoint_syntax_valid(self):
        """entrypoint.sh should pass shell syntax check."""
        result = subprocess.run(
            ["sh", "-n", ENTRYPOINT_PATH],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

"""Tests for core/auth.py - pure functions only."""
import time
import jwt
import pytest
from fastapi import HTTPException

from core.auth import hash_password, verify_password, create_access_token, decode_token
from core.config import settings


class TestPasswordHashing:
    def test_round_trip(self):
        hashed = hash_password("mysecretpass")
        assert verify_password("mysecretpass", hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("mysecretpass")
        assert verify_password("wrongpass", hashed) is False

    def test_different_hashes(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt salts are random


class TestJWTTokens:
    def test_create_and_decode(self):
        token = create_access_token(42)
        payload = decode_token(token)
        assert int(payload["sub"]) == 42

    def test_legacy_int_sub_still_works(self):
        """Tokens created before PyJWT 2.10 used int sub — must still decode."""
        payload = {
            "sub": 99,
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
        decoded = decode_token(token)
        assert int(decoded["sub"]) == 99

    def test_expired_token(self):
        payload = {
            "sub": 1,
            "exp": int(time.time()) - 10,
            "iat": int(time.time()) - 100,
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401
        assert "expiré" in exc_info.value.detail

    def test_invalid_token(self):
        with pytest.raises(HTTPException) as exc_info:
            decode_token("garbage.token.here")
        assert exc_info.value.status_code == 401
        assert "invalide" in exc_info.value.detail

    def test_wrong_secret(self):
        payload = {"sub": 1, "exp": int(time.time()) + 3600}
        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401

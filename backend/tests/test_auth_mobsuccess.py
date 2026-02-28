"""Tests for Mobsuccess Cognito JWT auth integration in core/auth.py."""
import base64
import json
import time
from unittest.mock import patch, MagicMock

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.auth import (
    get_current_user,
    _decode_cognito_jwt,
    _validate_cognito_token,
    _cognito_jwks_cache,
    create_access_token,
)
from database import Base, User


# ---------------------------------------------------------------------------
# RSA key pair for testing Cognito JWT signature verification
# ---------------------------------------------------------------------------

_test_rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_test_rsa_public = _test_rsa_key.public_key()

# Build JWKS response from the test key
_test_kid = "test-kid-001"


def _build_jwks():
    """Build a JWKS dict from our test RSA public key."""
    from jwt.algorithms import RSAAlgorithm
    jwk = json.loads(RSAAlgorithm.to_jwk(_test_rsa_public))
    jwk["kid"] = _test_kid
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return {"keys": [jwk]}


def _make_cognito_jwt(payload: dict) -> str:
    """Build a properly signed RS256 JWT (like Cognito would issue)."""
    return pyjwt.encode(
        payload,
        _test_rsa_key,
        algorithm="RS256",
        headers={"kid": _test_kid},
    )


def _make_credentials(token: str):
    creds = MagicMock()
    creds.credentials = token
    return creds


def _mock_jwks():
    """Inject test JWKS into the cache so _decode_cognito_jwt doesn't fetch."""
    issuer = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_xxx"
    _cognito_jwks_cache[f"{issuer}/.well-known/jwks.json"] = _build_jwks()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def cognito_payload():
    return {
        "sub": "abc-123-def-456",
        "email": "chloe@mobsuccess.com",
        "name": "Chloé Dupont",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "iss": "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_xxx",
        "token_use": "id",
    }


@pytest.fixture(autouse=True)
def inject_jwks():
    """Auto-inject test JWKS before each test."""
    _mock_jwks()
    yield
    # Clean up cache
    _cognito_jwks_cache.clear()


# ---------------------------------------------------------------------------
# Tests: _decode_cognito_jwt
# ---------------------------------------------------------------------------

class TestDecodeCognitoJwt:
    def test_decode_valid_jwt(self, cognito_payload):
        token = _make_cognito_jwt(cognito_payload)
        decoded = _decode_cognito_jwt(token)
        assert decoded["sub"] == "abc-123-def-456"
        assert decoded["email"] == "chloe@mobsuccess.com"

    def test_decode_invalid_signature(self, cognito_payload):
        """Token signed with a different key should fail."""
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = pyjwt.encode(
            cognito_payload, other_key, algorithm="RS256",
            headers={"kid": _test_kid},
        )
        with pytest.raises(ValueError, match="Invalid Cognito token"):
            _decode_cognito_jwt(token)

    def test_decode_invalid_token(self):
        with pytest.raises(ValueError):
            _decode_cognito_jwt("not-a-jwt")

    def test_decode_expired_token(self, cognito_payload):
        cognito_payload["exp"] = int(time.time()) - 100
        token = _make_cognito_jwt(cognito_payload)
        with pytest.raises(ValueError, match="expired"):
            _decode_cognito_jwt(token)

    def test_decode_non_cognito_issuer(self, cognito_payload):
        cognito_payload["iss"] = "https://evil.example.com"
        token = _make_cognito_jwt(cognito_payload)
        with pytest.raises(ValueError, match="Not a Cognito token"):
            _decode_cognito_jwt(token)


# ---------------------------------------------------------------------------
# Tests: _validate_cognito_token
# ---------------------------------------------------------------------------

class TestValidateCognitoToken:
    def test_creates_user(self, db_session, cognito_payload):
        token = _make_cognito_jwt(cognito_payload)
        user = _validate_cognito_token(token, db_session)

        assert user.email == "chloe@mobsuccess.com"
        assert user.name == "Chloé Dupont"
        assert user.is_active is True
        assert db_session.query(User).filter(User.email == "chloe@mobsuccess.com").count() == 1

    def test_updates_existing_user_by_email(self, db_session, cognito_payload):
        existing = User(
            email="chloe@mobsuccess.com",
            name="Old Name",
            password_hash="some-hash",
            is_active=True,
        )
        db_session.add(existing)
        db_session.commit()

        token = _make_cognito_jwt(cognito_payload)
        user = _validate_cognito_token(token, db_session)

        assert user.id == existing.id
        assert user.name == "Chloé Dupont"
        assert user.email == "chloe@mobsuccess.com"

    def test_expired_token_raises_401(self, db_session, cognito_payload):
        cognito_payload["exp"] = int(time.time()) - 100
        token = _make_cognito_jwt(cognito_payload)

        with pytest.raises(HTTPException) as exc_info:
            _validate_cognito_token(token, db_session)
        assert exc_info.value.status_code == 401

    def test_missing_sub_raises_401(self, db_session, cognito_payload):
        del cognito_payload["sub"]
        token = _make_cognito_jwt(cognito_payload)

        with pytest.raises(HTTPException) as exc_info:
            _validate_cognito_token(token, db_session)
        assert exc_info.value.status_code == 401

    def test_invalid_token_raises_401(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            _validate_cognito_token("not-a-jwt", db_session)
        assert exc_info.value.status_code == 401

    def test_deterministic_ms_user_id(self, db_session, cognito_payload):
        """ms_user_id should be deterministic (SHA-256 based, not hash())."""
        token = _make_cognito_jwt(cognito_payload)
        user1 = _validate_cognito_token(token, db_session)
        ms_id_1 = user1.ms_user_id

        # Same sub should produce same ms_user_id
        import hashlib
        expected = int(hashlib.sha256("abc-123-def-456".encode()).hexdigest()[:8], 16)
        assert ms_id_1 == expected


# ---------------------------------------------------------------------------
# Tests: get_current_user fallback chain
# ---------------------------------------------------------------------------

class TestGetCurrentUserFallback:
    def test_jwt_local_still_works(self, db_session):
        user = User(
            email="local@test.com",
            name="Local User",
            password_hash="hashed",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        token = create_access_token(user.id)
        creds = _make_credentials(token)

        result = get_current_user(credentials=creds, db=db_session)
        assert result.id == user.id

    @patch("core.auth.settings")
    def test_fallback_jwt_then_cognito(self, mock_settings, db_session, cognito_payload):
        """Invalid local JWT + valid Cognito token → user from Cognito."""
        mock_settings.MS_AUTH_ENABLED = True
        mock_settings.JWT_SECRET = settings.JWT_SECRET

        cognito_token = _make_cognito_jwt(cognito_payload)
        creds = _make_credentials(cognito_token)

        result = get_current_user(credentials=creds, db=db_session)
        assert result.email == "chloe@mobsuccess.com"
        assert result.name == "Chloé Dupont"

    @patch("core.auth.settings")
    def test_mobsuccess_disabled_only_jwt(self, mock_settings, db_session):
        mock_settings.MS_AUTH_ENABLED = False
        mock_settings.JWT_SECRET = settings.JWT_SECRET

        creds = _make_credentials("not-a-jwt-token")

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=creds, db=db_session)
        assert exc_info.value.status_code == 401

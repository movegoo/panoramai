"""Tests for Mobsuccess Cognito JWT auth integration in core/auth.py."""
import base64
import json
import time
from unittest.mock import patch, MagicMock

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.auth import (
    get_current_user,
    _decode_cognito_jwt,
    _validate_cognito_token,
    create_access_token,
)
from database import Base, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cognito_jwt(payload: dict, header: dict | None = None) -> str:
    """Build a fake Cognito JWT (3-part base64url, no real signature)."""
    header = header or {"alg": "RS256", "typ": "JWT", "kid": "DhUAkad"}
    def b64url(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()
    return f"{b64url(header)}.{b64url(payload)}.fake-signature"


def _make_credentials(token: str):
    creds = MagicMock()
    creds.credentials = token
    return creds


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


# ---------------------------------------------------------------------------
# Tests: _decode_cognito_jwt
# ---------------------------------------------------------------------------

class TestDecodeCognitoJwt:
    def test_decode_valid_jwt(self, cognito_payload):
        token = _make_cognito_jwt(cognito_payload)
        decoded = _decode_cognito_jwt(token)
        assert decoded["sub"] == "abc-123-def-456"
        assert decoded["email"] == "chloe@mobsuccess.com"

    def test_decode_invalid_token(self):
        with pytest.raises(ValueError, match="Not a valid JWT"):
            _decode_cognito_jwt("not-a-jwt")

    def test_decode_two_parts(self):
        with pytest.raises(ValueError, match="Not a valid JWT"):
            _decode_cognito_jwt("part1.part2")


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
        assert "expiré" in exc_info.value.detail

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

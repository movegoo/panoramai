"""Tests for Mobsuccess Lambda Authorizer integration in core/auth.py."""
import time
from unittest.mock import patch, MagicMock

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, Session

from core.config import settings
from core.auth import (
    get_current_user,
    _validate_mobsuccess_token,
    create_access_token,
)
from database import Base, User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    """In-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def ms_lambda_response():
    """Standard successful Mobsuccess Lambda response."""
    return {
        "isAuthorized": True,
        "context": {
            "id_user": 12345,
            "admin": True,
            "firstname": "Jean",
            "lastname": "Dupont",
            "email": "jean@mobsuccess.com",
            "ms_rights": {"some": "rights"},
        },
    }


def _make_credentials(token: str):
    """Build a mock HTTPAuthorizationCredentials."""
    creds = MagicMock()
    creds.credentials = token
    return creds


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMobsuccessValidToken:
    @patch("core.auth.httpx.post")
    def test_creates_user(self, mock_post, db_session, ms_lambda_response):
        """A valid Mobsuccess token should create a new local user."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = ms_lambda_response
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        user = _validate_mobsuccess_token("ms-token-abc", db_session)

        assert user.email == "jean@mobsuccess.com"
        assert user.name == "Jean Dupont"
        assert user.ms_user_id == 12345
        assert user.is_admin is True
        assert user.password_hash == "ms-auth"

        # Verify persisted
        assert db_session.query(User).filter(User.ms_user_id == 12345).count() == 1

    @patch("core.auth.httpx.post")
    def test_updates_existing_user(self, mock_post, db_session, ms_lambda_response):
        """If a user with the same ms_user_id exists, update their info."""
        existing = User(
            email="old@mobsuccess.com",
            name="Old Name",
            password_hash="ms-auth",
            ms_user_id=12345,
            is_admin=False,
            is_active=True,
        )
        db_session.add(existing)
        db_session.commit()

        mock_resp = MagicMock()
        mock_resp.json.return_value = ms_lambda_response
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        user = _validate_mobsuccess_token("ms-token-abc", db_session)

        assert user.id == existing.id
        assert user.email == "jean@mobsuccess.com"
        assert user.name == "Jean Dupont"
        assert user.is_admin is True

    @patch("core.auth.httpx.post")
    def test_matches_by_email_fallback(self, mock_post, db_session, ms_lambda_response):
        """If no ms_user_id match, fall back to email matching."""
        existing = User(
            email="jean@mobsuccess.com",
            name="Old Name",
            password_hash="some-hash",
            is_active=True,
        )
        db_session.add(existing)
        db_session.commit()

        mock_resp = MagicMock()
        mock_resp.json.return_value = ms_lambda_response
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        user = _validate_mobsuccess_token("ms-token-abc", db_session)

        assert user.id == existing.id
        assert user.ms_user_id == 12345
        assert user.name == "Jean Dupont"


class TestMobsuccessUnauthorized:
    @patch("core.auth.httpx.post")
    def test_unauthorized_returns_401(self, mock_post, db_session):
        """isAuthorized=false should raise 401."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"isAuthorized": False, "context": {}}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        with pytest.raises(HTTPException) as exc_info:
            _validate_mobsuccess_token("bad-token", db_session)
        assert exc_info.value.status_code == 401

    @patch("core.auth.httpx.post")
    def test_lambda_error_returns_401(self, mock_post, db_session):
        """Lambda HTTP error (500, timeout) should raise 401."""
        mock_post.side_effect = Exception("Connection timeout")

        with pytest.raises(HTTPException) as exc_info:
            _validate_mobsuccess_token("bad-token", db_session)
        assert exc_info.value.status_code == 401


class TestGetCurrentUserFallback:
    def test_jwt_local_still_works(self, db_session):
        """A valid local JWT should work regardless of MS_AUTH_ENABLED."""
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

        with patch("core.auth.get_db", return_value=iter([db_session])):
            result = get_current_user(credentials=creds, db=db_session)
        assert result.id == user.id

    @patch("core.auth.settings")
    @patch("core.auth.httpx.post")
    def test_fallback_jwt_then_mobsuccess(self, mock_post, mock_settings, db_session, ms_lambda_response):
        """Invalid JWT + valid Mobsuccess token → user from Lambda."""
        mock_settings.MS_AUTH_ENABLED = True
        mock_settings.MS_LAMBDA_AUTHORIZER_URL = "https://lambda.example.com/"
        mock_settings.JWT_SECRET = settings.JWT_SECRET

        mock_resp = MagicMock()
        mock_resp.json.return_value = ms_lambda_response
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        creds = _make_credentials("not-a-jwt-token")

        result = get_current_user(credentials=creds, db=db_session)
        assert result.ms_user_id == 12345
        assert result.email == "jean@mobsuccess.com"

    @patch("core.auth.settings")
    def test_mobsuccess_disabled_only_jwt(self, mock_settings, db_session):
        """MS_AUTH_ENABLED=false → Mobsuccess token should 401."""
        mock_settings.MS_AUTH_ENABLED = False
        mock_settings.MS_LAMBDA_AUTHORIZER_URL = ""
        mock_settings.JWT_SECRET = settings.JWT_SECRET

        creds = _make_credentials("not-a-jwt-token")

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=creds, db=db_session)
        assert exc_info.value.status_code == 401

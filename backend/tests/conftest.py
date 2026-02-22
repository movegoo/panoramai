"""Shared test fixtures."""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Force test settings before any app imports
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["JWT_EXPIRATION_DAYS"] = "1"

from database import Base, get_db, User, Advertiser, Competitor, UserAdvertiser, AdvertiserCompetitor
from core.auth import hash_password, create_access_token
from main import app

from fastapi.testclient import TestClient


TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def db():
    """Direct DB session for test setup."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db):
    """Create a test user and return (user, token)."""
    user = User(
        email="test@example.com",
        name="Test User",
        password_hash=hash_password("password123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return user, token


@pytest.fixture
def auth_headers(test_user):
    """Authorization headers for authenticated requests."""
    _, token = test_user
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_advertiser(db, test_user):
    """Create an Advertiser + UserAdvertiser link for the test user."""
    user, _ = test_user
    adv = Advertiser(company_name="Test Brand", sector="supermarche", is_active=True)
    db.add(adv)
    db.commit()
    db.refresh(adv)
    link = UserAdvertiser(user_id=user.id, advertiser_id=adv.id, role="owner")
    db.add(link)
    db.commit()
    return adv


@pytest.fixture
def test_competitor(db, test_advertiser):
    """Create a Competitor + AdvertiserCompetitor link."""
    comp = Competitor(name="Carrefour", website="https://carrefour.fr", is_active=True)
    db.add(comp)
    db.commit()
    db.refresh(comp)
    link = AdvertiserCompetitor(advertiser_id=test_advertiser.id, competitor_id=comp.id)
    db.add(link)
    db.commit()
    return comp


@pytest.fixture
def adv_headers(auth_headers, test_advertiser):
    """Auth headers with X-Advertiser-Id."""
    return {**auth_headers, "X-Advertiser-Id": str(test_advertiser.id)}


@pytest.fixture
def second_user(db):
    """A second user with no shared access (for isolation tests)."""
    user = User(
        email="other@example.com",
        name="Other User",
        password_hash=hash_password("password123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return user, token

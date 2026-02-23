"""Tests for advertiser migrate-links endpoint."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.advertiser import router


def make_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/advertiser")
    return app


def make_advertiser(adv_id, user_id, name="Test Corp"):
    adv = MagicMock()
    adv.id = adv_id
    adv.user_id = user_id
    adv.company_name = name
    adv.is_active = True
    return adv


def test_migrate_creates_missing_links():
    """Test that migrate-links creates UserAdvertiser for orphan advertisers."""
    app = make_app()
    db = MagicMock()

    adv1 = make_advertiser(10, user_id=15, name="Carrefour")
    adv2 = make_advertiser(11, user_id=15, name="Auchan")

    # query(Advertiser).filter(...).all() returns advertisers with user_id
    # query(UserAdvertiser).filter(...).first() returns None (no link exists)
    def mock_query(model):
        q = MagicMock()
        from database import Advertiser, UserAdvertiser
        if model == Advertiser:
            q.filter.return_value.all.return_value = [adv1, adv2]
        elif model == UserAdvertiser:
            q.filter.return_value.first.return_value = None  # No existing link
        return q

    db.query = mock_query

    from database import get_db
    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)
    resp = client.post("/api/advertiser/migrate-links")

    assert resp.status_code == 200
    data = resp.json()
    assert data["created_links"] == 2
    assert data["skipped_existing"] == 0
    assert len(data["created"]) == 2
    assert data["created"][0]["name"] == "Carrefour"
    assert data["created"][1]["name"] == "Auchan"
    db.commit.assert_called_once()


def test_migrate_skips_existing_links():
    """Test that existing links are not duplicated."""
    app = make_app()
    db = MagicMock()

    adv1 = make_advertiser(10, user_id=15, name="Sephora")

    def mock_query(model):
        q = MagicMock()
        from database import Advertiser, UserAdvertiser
        if model == Advertiser:
            q.filter.return_value.all.return_value = [adv1]
        elif model == UserAdvertiser:
            # Link already exists
            q.filter.return_value.first.return_value = MagicMock()
        return q

    db.query = mock_query

    from database import get_db
    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)
    resp = client.post("/api/advertiser/migrate-links")

    assert resp.status_code == 200
    data = resp.json()
    assert data["created_links"] == 0
    assert data["skipped_existing"] == 1
    assert data["skipped"][0]["name"] == "Sephora"


def test_migrate_no_orphan_advertisers():
    """Test with no advertisers that have user_id set."""
    app = make_app()
    db = MagicMock()

    def mock_query(model):
        q = MagicMock()
        q.filter.return_value.all.return_value = []
        return q

    db.query = mock_query

    from database import get_db
    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)
    resp = client.post("/api/advertiser/migrate-links")

    assert resp.status_code == 200
    data = resp.json()
    assert data["created_links"] == 0
    assert data["skipped_existing"] == 0


def test_migrate_mixed_create_and_skip():
    """Test with some links existing and some not."""
    app = make_app()
    db = MagicMock()

    adv_existing = make_advertiser(2, user_id=15, name="Sephora")
    adv_new = make_advertiser(10, user_id=15, name="Carrefour")

    ua_lookup_results = iter([MagicMock(), None])  # Sephora exists, Carrefour doesn't

    def mock_query(model):
        from database import Advertiser, UserAdvertiser
        if model == Advertiser:
            q = MagicMock()
            q.filter.return_value.all.return_value = [adv_existing, adv_new]
            return q
        elif model == UserAdvertiser:
            q = MagicMock()
            q.filter.return_value.first.return_value = next(ua_lookup_results)
            return q
        return MagicMock()

    db.query = mock_query

    from database import get_db
    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)
    resp = client.post("/api/advertiser/migrate-links")

    assert resp.status_code == 200
    data = resp.json()
    assert data["created_links"] == 1
    assert data["skipped_existing"] == 1
    assert data["created"][0]["name"] == "Carrefour"
    assert data["skipped"][0]["name"] == "Sephora"

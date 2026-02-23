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


def make_competitor(comp_id, advertiser_id, name="Rival Inc", is_brand=False):
    comp = MagicMock()
    comp.id = comp_id
    comp.advertiser_id = advertiser_id
    comp.name = name
    comp.is_active = True
    comp.is_brand = is_brand
    return comp


# ─── User-Advertiser migration ─────────────────────────────────


def test_migrate_creates_missing_ua_links():
    """Test that migrate-links creates UserAdvertiser for orphan advertisers."""
    app = make_app()
    db = MagicMock()

    adv1 = make_advertiser(10, user_id=15, name="Carrefour")
    adv2 = make_advertiser(11, user_id=15, name="Auchan")

    from database import Advertiser, UserAdvertiser, AdvertiserCompetitor, Competitor

    def mock_query(model):
        q = MagicMock()
        if model == Advertiser:
            q.filter.return_value.all.return_value = [adv1, adv2]
        elif model == UserAdvertiser:
            q.filter.return_value.first.return_value = None  # No existing link
        elif model == Competitor:
            q.filter.return_value.all.return_value = []  # No competitors
        elif model == AdvertiserCompetitor:
            q.filter.return_value.first.return_value = None
        return q

    db.query = mock_query

    from database import get_db
    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)
    resp = client.post("/api/advertiser/migrate-links")

    assert resp.status_code == 200
    data = resp.json()
    assert data["user_advertisers"]["created"] == 2
    assert data["user_advertisers"]["skipped"] == 0
    db.commit.assert_called_once()


def test_migrate_skips_existing_ua_links():
    """Test that existing user-advertiser links are not duplicated."""
    app = make_app()
    db = MagicMock()

    adv1 = make_advertiser(2, user_id=15, name="Sephora")

    from database import Advertiser, UserAdvertiser, AdvertiserCompetitor, Competitor

    def mock_query(model):
        q = MagicMock()
        if model == Advertiser:
            q.filter.return_value.all.return_value = [adv1]
        elif model == UserAdvertiser:
            q.filter.return_value.first.return_value = MagicMock()  # Link exists
        elif model == Competitor:
            q.filter.return_value.all.return_value = []
        elif model == AdvertiserCompetitor:
            q.filter.return_value.first.return_value = None
        return q

    db.query = mock_query

    from database import get_db
    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)
    resp = client.post("/api/advertiser/migrate-links")

    assert resp.status_code == 200
    data = resp.json()
    assert data["user_advertisers"]["created"] == 0
    assert data["user_advertisers"]["skipped"] == 1


# ─── Advertiser-Competitor migration ───────────────────────────


def test_migrate_creates_missing_ac_links():
    """Test that migrate creates AdvertiserCompetitor for orphan competitors."""
    app = make_app()
    db = MagicMock()

    comp1 = make_competitor(100, advertiser_id=2, name="Dior")
    comp2 = make_competitor(101, advertiser_id=2, name="Chanel")

    from database import Advertiser, UserAdvertiser, AdvertiserCompetitor, Competitor

    def mock_query(model):
        q = MagicMock()
        if model == Advertiser:
            q.filter.return_value.all.return_value = []
        elif model == UserAdvertiser:
            q.filter.return_value.first.return_value = None
        elif model == Competitor:
            q.filter.return_value.all.return_value = [comp1, comp2]
        elif model == AdvertiserCompetitor:
            q.filter.return_value.first.return_value = None  # No existing link
        return q

    db.query = mock_query

    from database import get_db
    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)
    resp = client.post("/api/advertiser/migrate-links")

    assert resp.status_code == 200
    data = resp.json()
    assert data["advertiser_competitors"]["created"] == 2
    assert data["advertiser_competitors"]["skipped"] == 0


def test_migrate_empty_db():
    """Test with no advertisers or competitors in DB."""
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
    assert data["user_advertisers"]["created"] == 0
    assert data["advertiser_competitors"]["created"] == 0

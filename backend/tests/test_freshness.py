"""Tests for the freshness router."""
from datetime import datetime


def test_freshness_returns_all_keys(client, adv_headers):
    """Freshness returns all expected source keys."""
    resp = client.get("/api/freshness", headers=adv_headers)
    assert resp.status_code == 200
    data = resp.json()
    for key in ["instagram", "tiktok", "youtube", "playstore", "appstore", "ads_meta", "ads_google", "ads_snapchat"]:
        assert key in data


def test_freshness_returns_null_if_no_data(client, adv_headers):
    """Freshness returns null for sources with no data."""
    resp = client.get("/api/freshness", headers=adv_headers)
    assert resp.status_code == 200
    data = resp.json()
    for value in data.values():
        assert value is None


def test_freshness_returns_timestamp_with_data(client, adv_headers, test_competitor, db):
    """Freshness returns real timestamps when data exists."""
    from database import InstagramData
    now = datetime.utcnow()
    db.add(InstagramData(competitor_id=test_competitor.id, followers=1000, following=100, posts_count=50, recorded_at=now))
    db.commit()

    resp = client.get("/api/freshness", headers=adv_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["instagram"] is not None
    assert data["tiktok"] is None


def test_freshness_requires_auth(client):
    """Freshness requires authentication."""
    resp = client.get("/api/freshness")
    assert resp.status_code in (401, 403)

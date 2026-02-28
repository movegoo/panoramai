"""Tests for routers/youtube.py — YouTube API endpoints."""
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from database import Competitor, YouTubeData, Advertiser, UserAdvertiser, AdvertiserCompetitor


# ─── Helper ───────────────────────────────────────────────────────

def _setup_data(db, test_user, test_advertiser):
    """Create a competitor with youtube data."""
    user, _ = test_user
    comp = Competitor(name="Leclerc", youtube_channel_id="UCxxx", is_active=True)
    db.add(comp)
    db.commit()
    db.refresh(comp)
    db.add(AdvertiserCompetitor(advertiser_id=test_advertiser.id, competitor_id=comp.id))
    db.commit()
    return comp


# ─── GET /data/{competitor_id} ───────────────────────────────────

class TestYouTubeHistory:
    def test_returns_data(self, client, db, test_user, test_advertiser, adv_headers):
        comp = _setup_data(db, test_user, test_advertiser)
        db.add(YouTubeData(competitor_id=comp.id, channel_id="UCxxx", subscribers=50000, total_views=1000000, videos_count=100, recorded_at=datetime.utcnow()))
        db.commit()

        resp = client.get(f"/api/youtube/data/{comp.id}", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["subscribers"] == 50000

    def test_empty_data(self, client, db, test_user, test_advertiser, adv_headers):
        comp = _setup_data(db, test_user, test_advertiser)
        resp = client.get(f"/api/youtube/data/{comp.id}", headers=adv_headers)
        assert resp.status_code == 200
        assert resp.json() == []


# ─── GET /latest/{competitor_id} ─────────────────────────────────

class TestYouTubeLatest:
    def test_returns_latest(self, client, db, test_user, test_advertiser, adv_headers):
        comp = _setup_data(db, test_user, test_advertiser)
        db.add(YouTubeData(competitor_id=comp.id, channel_id="UCxxx", subscribers=40000, total_views=800000, videos_count=90, recorded_at=datetime.utcnow() - timedelta(days=7)))
        db.add(YouTubeData(competitor_id=comp.id, channel_id="UCxxx", subscribers=50000, total_views=1000000, videos_count=100, recorded_at=datetime.utcnow()))
        db.commit()

        resp = client.get(f"/api/youtube/latest/{comp.id}", headers=adv_headers)
        assert resp.status_code == 200
        assert resp.json()["subscribers"] == 50000

    def test_404_when_no_data(self, client, db, test_user, test_advertiser, adv_headers):
        comp = _setup_data(db, test_user, test_advertiser)
        resp = client.get(f"/api/youtube/latest/{comp.id}", headers=adv_headers)
        assert resp.status_code == 404


# ─── POST /fetch/{competitor_id} ─────────────────────────────────

class TestYouTubeFetch:
    def test_fetch_success(self, client, db, test_user, test_advertiser, adv_headers):
        comp = _setup_data(db, test_user, test_advertiser)
        with patch("routers.youtube.youtube_api") as mock_yt:
            mock_yt.get_channel_analytics = AsyncMock(return_value={
                "success": True,
                "channel_name": "Leclerc",
                "subscribers": 60000,
                "total_views": 1200000,
                "videos_count": 110,
                "description": "Official",
                "analytics": {
                    "avg_views": 5000,
                    "avg_likes": 200,
                    "avg_comments": 30,
                    "engagement_rate": 4.5,
                },
            })
            resp = client.post(f"/api/youtube/fetch/{comp.id}", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["subscribers"] == 60000

    def test_fetch_no_channel_id(self, client, db, test_user, test_advertiser, adv_headers):
        comp = _setup_data(db, test_user, test_advertiser)
        comp.youtube_channel_id = None
        db.commit()
        resp = client.post(f"/api/youtube/fetch/{comp.id}", headers=adv_headers)
        assert resp.status_code == 400

    def test_fetch_api_failure(self, client, db, test_user, test_advertiser, adv_headers):
        comp = _setup_data(db, test_user, test_advertiser)
        with patch("routers.youtube.youtube_api") as mock_yt:
            mock_yt.get_channel_analytics = AsyncMock(return_value={
                "success": False,
                "error": "API quota exceeded",
            })
            resp = client.post(f"/api/youtube/fetch/{comp.id}", headers=adv_headers)
        assert resp.status_code == 500


# ─── GET /trends/{competitor_id} ─────────────────────────────────

class TestYouTubeTrends:
    def test_trends_with_data(self, client, db, test_user, test_advertiser, adv_headers):
        comp = _setup_data(db, test_user, test_advertiser)
        db.add(YouTubeData(competitor_id=comp.id, channel_id="UCxxx", subscribers=40000, total_views=800000, videos_count=90, recorded_at=datetime.utcnow() - timedelta(days=7)))
        db.add(YouTubeData(competitor_id=comp.id, channel_id="UCxxx", subscribers=50000, total_views=1000000, videos_count=100, recorded_at=datetime.utcnow()))
        db.commit()

        resp = client.get(f"/api/youtube/trends/{comp.id}", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "current" in data
        assert "trends" in data
        assert data["current"]["subscribers"] == 50000

    def test_trends_no_data(self, client, db, test_user, test_advertiser, adv_headers):
        comp = _setup_data(db, test_user, test_advertiser)
        resp = client.get(f"/api/youtube/trends/{comp.id}", headers=adv_headers)
        assert resp.status_code == 404


# ─── GET /videos/{competitor_id} ─────────────────────────────────

class TestYouTubeVideos:
    def test_success(self, client, db, test_user, test_advertiser, adv_headers):
        comp = _setup_data(db, test_user, test_advertiser)
        with patch("routers.youtube.youtube_api") as mock_yt:
            mock_yt.fetch_recent_videos = AsyncMock(return_value={
                "success": True,
                "videos": [{"id": "v1", "title": "Test"}],
            })
            resp = client.get(f"/api/youtube/videos/{comp.id}", headers=adv_headers)
        assert resp.status_code == 200
        assert resp.json()["videos"][0]["id"] == "v1"

    def test_no_channel(self, client, db, test_user, test_advertiser, adv_headers):
        comp = _setup_data(db, test_user, test_advertiser)
        comp.youtube_channel_id = None
        db.commit()
        resp = client.get(f"/api/youtube/videos/{comp.id}", headers=adv_headers)
        assert resp.status_code == 400


# ─── GET /search ──────────────────────────────────────────────────

class TestYouTubeSearch:
    def test_search(self, client, auth_headers):
        with patch("routers.youtube.youtube_api") as mock_yt:
            mock_yt.search_channels = AsyncMock(return_value={
                "success": True,
                "channels": [{"id": "UC1", "title": "Channel"}],
            })
            resp = client.get("/api/youtube/search?query=test", headers=auth_headers)
        assert resp.status_code == 200

    def test_search_failure(self, client, auth_headers):
        with patch("routers.youtube.youtube_api") as mock_yt:
            mock_yt.search_channels = AsyncMock(return_value={
                "success": False,
                "error": "Quota exceeded",
            })
            resp = client.get("/api/youtube/search?query=test", headers=auth_headers)
        assert resp.status_code == 500


# ─── GET /channel/{channel_id} ───────────────────────────────────

class TestYouTubeChannel:
    def test_success(self, client, auth_headers):
        with patch("routers.youtube.youtube_api") as mock_yt:
            mock_yt.get_channel_analytics = AsyncMock(return_value={
                "success": True,
                "channel_name": "Test",
                "subscribers": 10000,
            })
            resp = client.get("/api/youtube/channel/UCtest", headers=auth_headers)
        assert resp.status_code == 200

    def test_failure(self, client, auth_headers):
        with patch("routers.youtube.youtube_api") as mock_yt:
            mock_yt.get_channel_analytics = AsyncMock(return_value={
                "success": False,
                "error": "Channel not found",
            })
            resp = client.get("/api/youtube/channel/UCinvalid", headers=auth_headers)
        assert resp.status_code == 500

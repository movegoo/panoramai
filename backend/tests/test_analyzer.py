"""Tests for services/analyzer.py — Competitive analysis and rankings."""
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, Competitor, InstagramData, AppData, Ad
from services.analyzer import CompetitiveAnalyzer


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _add_competitor(db, name, instagram=None, facebook_page_id=None,
                    playstore_app_id=None, appstore_app_id=None, is_active=True):
    comp = Competitor(
        name=name,
        instagram_username=instagram,
        facebook_page_id=facebook_page_id,
        playstore_app_id=playstore_app_id,
        appstore_app_id=appstore_app_id,
        is_active=is_active,
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp


# ─── Instagram Rankings ──────────────────────────────────────────

class TestInstagramRankings:
    def test_empty_db(self, db_session):
        analyzer = CompetitiveAnalyzer(db_session)
        assert analyzer.get_instagram_rankings() == []

    def test_ranks_by_followers(self, db_session):
        c1 = _add_competitor(db_session, "Leclerc", instagram="leclerc")
        c2 = _add_competitor(db_session, "Carrefour", instagram="carrefour")

        db_session.add(InstagramData(competitor_id=c1.id, followers=50000, engagement_rate=3.0, posts_count=100, recorded_at=datetime.utcnow()))
        db_session.add(InstagramData(competitor_id=c2.id, followers=80000, engagement_rate=2.5, posts_count=200, recorded_at=datetime.utcnow()))
        db_session.commit()

        analyzer = CompetitiveAnalyzer(db_session)
        rankings = analyzer.get_instagram_rankings()

        assert len(rankings) == 2
        assert rankings[0]["name"] == "Carrefour"
        assert rankings[0]["rank"] == 1
        assert rankings[1]["name"] == "Leclerc"
        assert rankings[1]["rank"] == 2

    def test_skips_inactive(self, db_session):
        c = _add_competitor(db_session, "Inactive", instagram="inactive", is_active=False)
        db_session.add(InstagramData(competitor_id=c.id, followers=100000, engagement_rate=5.0, posts_count=50, recorded_at=datetime.utcnow()))
        db_session.commit()

        analyzer = CompetitiveAnalyzer(db_session)
        assert analyzer.get_instagram_rankings() == []

    def test_skips_without_instagram(self, db_session):
        _add_competitor(db_session, "NoIG", instagram=None)
        analyzer = CompetitiveAnalyzer(db_session)
        assert analyzer.get_instagram_rankings() == []


# ─── App Rankings ────────────────────────────────────────────────

class TestAppRankings:
    def test_empty_db(self, db_session):
        analyzer = CompetitiveAnalyzer(db_session)
        assert analyzer.get_app_rankings() == []

    def test_ranks_by_rating(self, db_session):
        c1 = _add_competitor(db_session, "App A", playstore_app_id="com.a")
        c2 = _add_competitor(db_session, "App B", playstore_app_id="com.b")

        db_session.add(AppData(competitor_id=c1.id, store="playstore", app_name="A", rating=4.5, reviews_count=1000, recorded_at=datetime.utcnow()))
        db_session.add(AppData(competitor_id=c2.id, store="playstore", app_name="B", rating=4.8, reviews_count=500, recorded_at=datetime.utcnow()))
        db_session.commit()

        analyzer = CompetitiveAnalyzer(db_session)
        rankings = analyzer.get_app_rankings("playstore")

        assert len(rankings) == 2
        assert rankings[0]["name"] == "App B"
        assert rankings[0]["rating"] == 4.8

    def test_appstore_rankings(self, db_session):
        c = _add_competitor(db_session, "iOS App", appstore_app_id="id123")
        db_session.add(AppData(competitor_id=c.id, store="appstore", app_name="iOS", rating=4.0, reviews_count=200, recorded_at=datetime.utcnow()))
        db_session.commit()

        analyzer = CompetitiveAnalyzer(db_session)
        rankings = analyzer.get_app_rankings("appstore")
        assert len(rankings) == 1


# ─── Ad Activity Comparison ──────────────────────────────────────

class TestAdActivityComparison:
    def test_empty(self, db_session):
        analyzer = CompetitiveAnalyzer(db_session)
        assert analyzer.get_ad_activity_comparison() == []

    def test_sorts_by_active_ads(self, db_session):
        c1 = _add_competitor(db_session, "Brand A", facebook_page_id="fp1")
        c2 = _add_competitor(db_session, "Brand B", facebook_page_id="fp2")

        for i in range(3):
            db_session.add(Ad(competitor_id=c1.id, ad_id=f"a{i}", is_active=True, platform="meta", created_at=datetime.utcnow()))
        db_session.add(Ad(competitor_id=c2.id, ad_id="b0", is_active=True, platform="meta", created_at=datetime.utcnow()))
        db_session.commit()

        analyzer = CompetitiveAnalyzer(db_session)
        result = analyzer.get_ad_activity_comparison()

        assert len(result) == 2
        assert result[0]["name"] == "Brand A"
        assert result[0]["active_ads"] == 3
        assert result[1]["active_ads"] == 1


# ─── Growth Trends ───────────────────────────────────────────────

class TestGrowthTrends:
    def test_no_data(self, db_session):
        c = _add_competitor(db_session, "Empty", instagram="empty")
        analyzer = CompetitiveAnalyzer(db_session)
        result = analyzer.get_growth_trends(c.id)
        assert result["instagram"] is None
        assert result["playstore"] is None
        assert result["new_ads"] == 0

    def test_instagram_growth(self, db_session):
        c = _add_competitor(db_session, "Growing", instagram="growing")
        db_session.add(InstagramData(competitor_id=c.id, followers=10000, engagement_rate=3.0, posts_count=100, recorded_at=datetime.utcnow() - timedelta(days=20)))
        db_session.add(InstagramData(competitor_id=c.id, followers=12000, engagement_rate=3.5, posts_count=110, recorded_at=datetime.utcnow()))
        db_session.commit()

        analyzer = CompetitiveAnalyzer(db_session)
        result = analyzer.get_growth_trends(c.id, days=30)

        assert result["instagram"] is not None
        assert result["instagram"]["growth_percent"] == 20.0
        assert result["instagram"]["growth_absolute"] == 2000

    def test_playstore_trend(self, db_session):
        c = _add_competitor(db_session, "App", playstore_app_id="com.app")
        db_session.add(AppData(competitor_id=c.id, store="playstore", app_name="App", rating=4.0, reviews_count=100, recorded_at=datetime.utcnow() - timedelta(days=20)))
        db_session.add(AppData(competitor_id=c.id, store="playstore", app_name="App", rating=4.5, reviews_count=200, recorded_at=datetime.utcnow()))
        db_session.commit()

        analyzer = CompetitiveAnalyzer(db_session)
        result = analyzer.get_growth_trends(c.id)
        assert result["playstore"]["rating_change"] == 0.5


# ─── Competitive Report ──────────────────────────────────────────

class TestCompetitiveReport:
    def test_empty_report(self, db_session):
        analyzer = CompetitiveAnalyzer(db_session)
        report = analyzer.generate_competitive_report()
        assert report["total_competitors"] == 0
        assert report["insights"] == []

    def test_report_with_data(self, db_session):
        c = _add_competitor(db_session, "Leclerc", instagram="leclerc", facebook_page_id="fp1", playstore_app_id="com.leclerc")
        db_session.add(InstagramData(competitor_id=c.id, followers=100000, engagement_rate=4.0, posts_count=500, recorded_at=datetime.utcnow()))
        db_session.add(AppData(competitor_id=c.id, store="playstore", app_name="Leclerc", rating=4.3, reviews_count=5000, recorded_at=datetime.utcnow()))
        db_session.add(Ad(competitor_id=c.id, ad_id="ad1", is_active=True, platform="meta", created_at=datetime.utcnow()))
        db_session.commit()

        analyzer = CompetitiveAnalyzer(db_session)
        report = analyzer.generate_competitive_report()

        assert report["total_competitors"] == 1
        assert len(report["instagram_rankings"]) == 1
        assert len(report["insights"]) >= 1

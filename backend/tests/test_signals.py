"""Tests for the signal detection engine (services/signals.py)."""
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, call

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from services.signals import (
    _fmt_pct,
    _pct_change,
    _severity,
    _linear_slope,
    _get_two_latest,
    _create_signal,
    _detect_instagram_signals,
    _detect_tiktok_signals,
    _detect_youtube_signals,
    _detect_app_signals,
    _detect_ad_signals,
    _detect_growth_trends,
    _detect_review_velocity,
    _detect_engagement_trends,
    _detect_posting_frequency,
    detect_all_signals,
    snapshot_active_ads,
    THRESHOLDS,
)


# ─── Helper factories ────────────────────────────────────────────

def _make_comp(id=1, name="Leclerc", is_brand=False, is_active=True, advertiser_id=1):
    c = MagicMock()
    c.id = id
    c.name = name
    c.is_brand = is_brand
    c.is_active = is_active
    c.advertiser_id = advertiser_id
    return c


def _make_ig(followers, engagement_rate=3.0, posts_count=100, hours_ago=0, competitor_id=1):
    r = MagicMock()
    r.competitor_id = competitor_id
    r.followers = followers
    r.engagement_rate = engagement_rate
    r.posts_count = posts_count
    r.recorded_at = datetime.utcnow() - timedelta(hours=hours_ago)
    return r


def _make_tiktok(followers, videos_count=50, hours_ago=0, competitor_id=1):
    r = MagicMock()
    r.competitor_id = competitor_id
    r.followers = followers
    r.videos_count = videos_count
    r.recorded_at = datetime.utcnow() - timedelta(hours=hours_ago)
    return r


def _make_yt(subscribers, hours_ago=0, competitor_id=1):
    r = MagicMock()
    r.competitor_id = competitor_id
    r.subscribers = subscribers
    r.recorded_at = datetime.utcnow() - timedelta(hours=hours_ago)
    return r


def _make_app(rating, reviews_count=1000, store="playstore", hours_ago=0, competitor_id=1):
    r = MagicMock()
    r.competitor_id = competitor_id
    r.rating = rating
    r.reviews_count = reviews_count
    r.store = store
    r.recorded_at = datetime.utcnow() - timedelta(hours=hours_ago)
    return r


# ─── Unit: _fmt_pct ──────────────────────────────────────────────

class TestFmtPct:
    def test_zero(self):
        assert _fmt_pct(0) == "0%"

    def test_positive_large(self):
        assert _fmt_pct(12.34) == "+12.3%"

    def test_negative_large(self):
        assert _fmt_pct(-7.5) == "-7.5%"

    def test_small_positive(self):
        assert _fmt_pct(0.15) == "+0.15%"

    def test_very_small(self):
        assert _fmt_pct(0.005) == "+0.005%"

    def test_negative_small(self):
        assert _fmt_pct(-0.05) == "-0.05%"


# ─── Unit: _pct_change ───────────────────────────────────────────

class TestPctChange:
    def test_normal(self):
        assert _pct_change(110, 100) == 10.0

    def test_decrease(self):
        assert _pct_change(90, 100) == -10.0

    def test_zero_old(self):
        assert _pct_change(100, 0) == 0

    def test_none_values(self):
        assert _pct_change(None, 100) == 0
        assert _pct_change(100, None) == 0


# ─── Unit: _severity ─────────────────────────────────────────────

class TestSeverity:
    def test_below_warning(self):
        assert _severity(3.0, 5.0, 15.0) is None

    def test_warning(self):
        assert _severity(7.0, 5.0, 15.0) == "warning"

    def test_critical(self):
        assert _severity(20.0, 5.0, 15.0) == "critical"

    def test_negative_critical(self):
        assert _severity(-16.0, 5.0, 15.0) == "critical"

    def test_exactly_at_warning(self):
        assert _severity(5.0, 5.0, 15.0) == "warning"


# ─── Unit: _linear_slope ─────────────────────────────────────────

class TestLinearSlope:
    def test_ascending(self):
        slope = _linear_slope([100, 200, 300, 400, 500])
        assert slope == pytest.approx(100.0)

    def test_flat(self):
        slope = _linear_slope([100, 100, 100, 100])
        assert slope == pytest.approx(0.0)

    def test_too_few_values(self):
        assert _linear_slope([1, 2]) == 0.0

    def test_descending(self):
        slope = _linear_slope([500, 400, 300])
        assert slope == pytest.approx(-100.0)


# ─── Unit: _get_two_latest ───────────────────────────────────────

class TestGetTwoLatest:
    def test_returns_none_with_one_record(self):
        """With only 1 record, function returns (None, None) since it needs 2."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database import Base, InstagramData
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()

        db.add(InstagramData(competitor_id=1, followers=1000, recorded_at=datetime.utcnow()))
        db.commit()

        latest, prev = _get_two_latest(db, InstagramData, 1)
        assert latest is None
        assert prev is None
        db.close()

    def test_returns_pair_with_gap(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database import Base, InstagramData
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()

        db.add(InstagramData(competitor_id=1, followers=1000, recorded_at=datetime.utcnow() - timedelta(hours=12)))
        db.add(InstagramData(competitor_id=1, followers=1100, recorded_at=datetime.utcnow()))
        db.commit()

        latest, prev = _get_two_latest(db, InstagramData, 1)
        assert latest.followers == 1100
        assert prev.followers == 1000
        db.close()

    def test_skips_records_without_enough_gap(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database import Base, InstagramData
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()

        now = datetime.utcnow()
        db.add(InstagramData(competitor_id=1, followers=1000, recorded_at=now - timedelta(hours=12)))
        db.add(InstagramData(competitor_id=1, followers=1050, recorded_at=now - timedelta(hours=1)))
        db.add(InstagramData(competitor_id=1, followers=1100, recorded_at=now))
        db.commit()

        latest, prev = _get_two_latest(db, InstagramData, 1, min_gap_hours=6)
        assert latest.followers == 1100
        assert prev.followers == 1000
        db.close()


# ─── Unit: _create_signal ────────────────────────────────────────

class TestCreateSignal:
    def test_creates_signal(self):
        db = MagicMock()
        comp = _make_comp()
        result = _create_signal(
            db, comp,
            signal_type="follower_spike",
            severity="warning",
            platform="instagram",
            title="Test signal",
        )
        assert result["type"] == "follower_spike"
        assert result["severity"] == "warning"
        assert result["competitor"] == "Leclerc"
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_brand_signals_downgraded_to_info(self):
        db = MagicMock()
        comp = _make_comp(is_brand=True)
        result = _create_signal(
            db, comp,
            signal_type="follower_spike",
            severity="critical",
            platform="instagram",
            title="Brand signal",
        )
        assert result["severity"] == "info"


# ─── Instagram signals ───────────────────────────────────────────

class TestInstagramSignals:
    def test_no_data_returns_empty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        comp = _make_comp()
        assert _detect_instagram_signals(db, comp) == []

    def test_follower_spike_detected(self):
        now = datetime.utcnow()
        latest = _make_ig(12000, hours_ago=0)
        prev = _make_ig(10000, hours_ago=24)
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [latest, prev]
        comp = _make_comp()

        signals = _detect_instagram_signals(db, comp)
        # 20% increase → critical
        assert len(signals) >= 1
        assert any(s["type"] == "follower_spike" for s in signals)

    def test_engagement_drop_detected(self):
        latest = _make_ig(10000, engagement_rate=1.0, hours_ago=0)
        prev = _make_ig(10000, engagement_rate=5.0, hours_ago=24)
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [latest, prev]
        comp = _make_comp()

        signals = _detect_instagram_signals(db, comp)
        assert any(s["type"] == "engagement_drop" for s in signals)

    def test_small_account_ignored(self):
        """Accounts with < min_followers are ignored."""
        latest = _make_ig(50, hours_ago=0)
        prev = _make_ig(10, hours_ago=24)  # 400% increase but too small
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [latest, prev]
        comp = _make_comp()

        signals = _detect_instagram_signals(db, comp)
        assert not any(s["type"].startswith("follower_") for s in signals)


# ─── TikTok signals ──────────────────────────────────────────────

class TestTikTokSignals:
    def test_follower_drop_detected(self):
        latest = _make_tiktok(8000, hours_ago=0)
        prev = _make_tiktok(10000, hours_ago=24)
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [latest, prev]
        comp = _make_comp()

        signals = _detect_tiktok_signals(db, comp)
        assert len(signals) >= 1
        assert signals[0]["type"] == "follower_drop"


# ─── YouTube signals ─────────────────────────────────────────────

class TestYouTubeSignals:
    def test_subscriber_spike(self):
        latest = _make_yt(12000, hours_ago=0)
        prev = _make_yt(10000, hours_ago=24)
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [latest, prev]
        comp = _make_comp()

        signals = _detect_youtube_signals(db, comp)
        assert len(signals) >= 1
        assert signals[0]["type"] == "subscriber_spike"


# ─── App signals ─────────────────────────────────────────────────

class TestAppSignals:
    def test_rating_drop_detected(self):
        latest = _make_app(3.5, hours_ago=0)
        prev = _make_app(4.2, hours_ago=24)
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [latest, prev]
        comp = _make_comp()

        signals = _detect_app_signals(db, comp)
        assert len(signals) >= 1
        assert signals[0]["type"] == "rating_drop"

    def test_rating_up_detected(self):
        latest = _make_app(4.8, hours_ago=0)
        prev = _make_app(4.0, hours_ago=24)
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [latest, prev]
        comp = _make_comp()

        signals = _detect_app_signals(db, comp)
        assert any(s["type"] == "rating_up" for s in signals)


# ─── Ad signals ──────────────────────────────────────────────────

class TestAdSignals:
    def test_ad_surge_detected(self):
        db = MagicMock()
        comp = _make_comp()
        # current_active = 20, prev_active = 5 → 300% increase
        db.query.return_value.filter.return_value.scalar.side_effect = [20, 5]
        # big_ads query = empty
        db.query.return_value.filter.return_value.all.return_value = []

        signals = _detect_ad_signals(db, comp)
        assert any(s["type"] == "ad_surge" for s in signals)

    def test_high_reach_campaign(self):
        db = MagicMock()
        comp = _make_comp()
        # ad counts
        db.query.return_value.filter.return_value.scalar.side_effect = [5, 5]
        # big ads
        big_ad = MagicMock()
        big_ad.ad_id = "ad_123"
        big_ad.eu_total_reach = 2_000_000
        big_ad.platform = "meta_ads"
        big_ad.ad_text = "Big sale!"
        db.query.return_value.filter.return_value.all.return_value = [big_ad]
        # no existing signal for this ad
        db.query.return_value.filter.return_value.first.return_value = None

        signals = _detect_ad_signals(db, comp)
        assert any(s["type"] == "high_reach_campaign" for s in signals)


# ─── snapshot_active_ads ─────────────────────────────────────────

class TestSnapshotActiveAds:
    def test_creates_snapshots(self):
        db = MagicMock()
        ad1 = MagicMock()
        ad1.ad_id = "a1"
        ad1.competitor_id = 1
        ad1.platform = "meta"
        ad1.is_active = True
        ad1.impressions_min = 100
        ad1.impressions_max = 200
        ad1.estimated_spend_min = 10
        ad1.estimated_spend_max = 50
        ad1.eu_total_reach = 5000
        db.query.return_value.filter.return_value.all.return_value = [ad1]

        count = snapshot_active_ads(db)
        assert count == 1
        db.add.assert_called_once()
        db.commit.assert_called_once()


# ─── detect_all_signals ──────────────────────────────────────────

class TestDetectAllSignals:
    def test_runs_all_detectors(self):
        db = MagicMock()
        comp = _make_comp()
        db.query.return_value.filter.return_value.all.return_value = [comp]
        # Make all sub-detectors return empty
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.scalar.side_effect = [0, 0]

        signals = detect_all_signals(db)
        assert isinstance(signals, list)

    def test_filters_by_advertiser(self):
        db = MagicMock()
        detect_all_signals(db, advertiser_id=42)
        # Should have called filter twice (is_active + advertiser_id)
        assert db.query.return_value.filter.called


# ─── Growth trends ───────────────────────────────────────────────

class TestGrowthTrends:
    def test_no_data_returns_empty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        # _already_signaled
        db.query.return_value.filter.return_value.first.return_value = None
        comp = _make_comp()

        signals = _detect_growth_trends(db, comp)
        assert signals == []


# ─── Review velocity ─────────────────────────────────────────────

class TestReviewVelocity:
    def test_no_data_returns_empty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value.filter.return_value.first.return_value = None
        comp = _make_comp()

        signals = _detect_review_velocity(db, comp)
        assert signals == []


# ─── Engagement trends ───────────────────────────────────────────

class TestEngagementTrends:
    def test_already_signaled_returns_empty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()  # exists
        comp = _make_comp()

        signals = _detect_engagement_trends(db, comp)
        assert signals == []


# ─── Posting frequency ───────────────────────────────────────────

class TestPostingFrequency:
    def test_no_data_returns_empty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value.filter.return_value.first.return_value = None
        comp = _make_comp()

        signals = _detect_posting_frequency(db, comp)
        assert signals == []

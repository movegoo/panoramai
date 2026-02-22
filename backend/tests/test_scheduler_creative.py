"""Tests for scheduled creative analysis."""
import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

from database import Ad


class NoCloseSession:
    """Wrapper that prevents close() from actually closing the session."""
    def __init__(self, real_db):
        self._db = real_db

    def __getattr__(self, name):
        if name == "close":
            return lambda: None  # no-op
        return getattr(self._db, name)


@pytest.mark.asyncio
async def test_daily_creative_analysis_processes_unanalyzed(db, test_competitor):
    """Scheduler analyzes unanalyzed ads with creative_url."""
    ad1 = Ad(competitor_id=test_competitor.id, ad_id="ad1", platform="facebook",
             creative_url="https://example.com/img1.jpg")
    ad2 = Ad(competitor_id=test_competitor.id, ad_id="ad2", platform="facebook",
             creative_url="https://example.com/img2.jpg")
    ad3 = Ad(competitor_id=test_competitor.id, ad_id="ad3", platform="facebook",
             creative_url="https://example.com/img3.jpg",
             creative_analyzed_at=datetime.utcnow(), creative_score=85)
    db.add_all([ad1, ad2, ad3])
    db.commit()

    mock_result = {
        "concept": "promo", "hook": "Super deal", "tone": "urgence",
        "text_overlay": "50%", "dominant_colors": ["#FF0000"],
        "has_product": True, "has_face": False, "has_logo": True,
        "layout": "hero", "cta_style": "bouton", "score": 78,
        "tags": ["promo"], "summary": "Good ad",
        "product_category": "Épicerie", "product_subcategory": "Café",
        "ad_objective": "conversion",
    }

    with patch("services.creative_analyzer.creative_analyzer.analyze_creative",
               new_callable=AsyncMock, return_value=mock_result):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)):
            await sched.daily_creative_analysis()

    result1 = db.query(Ad).filter(Ad.ad_id == "ad1").first()
    result2 = db.query(Ad).filter(Ad.ad_id == "ad2").first()
    result3 = db.query(Ad).filter(Ad.ad_id == "ad3").first()

    assert result1.creative_analyzed_at is not None
    assert result1.creative_score == 78
    assert result1.creative_concept == "promo"
    assert result2.creative_analyzed_at is not None
    assert result2.creative_score == 78
    assert result3.creative_score == 85


@pytest.mark.asyncio
async def test_daily_creative_analysis_skips_video(db, test_competitor):
    """Video ads are skipped during creative analysis."""
    ad = Ad(competitor_id=test_competitor.id, ad_id="vid1", platform="facebook",
            creative_url="https://example.com/video.mp4", display_format="VIDEO")
    db.add(ad)
    db.commit()

    with patch("services.creative_analyzer.creative_analyzer.analyze_creative",
               new_callable=AsyncMock) as mock_analyze:
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)):
            await sched.daily_creative_analysis()

    mock_analyze.assert_not_called()


@pytest.mark.asyncio
async def test_daily_creative_analysis_skips_google_syndication(db, test_competitor):
    """Ads with googlesyndication URLs are marked as non-analyzable."""
    ad = Ad(competitor_id=test_competitor.id, ad_id="gsyn1", platform="google",
            creative_url="https://pagead2.googlesyndication.com/something")
    db.add(ad)
    db.commit()

    with patch("services.creative_analyzer.creative_analyzer.analyze_creative",
               new_callable=AsyncMock) as mock_analyze:
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)):
            await sched.daily_creative_analysis()

    result = db.query(Ad).filter(Ad.ad_id == "gsyn1").first()
    assert result.creative_analyzed_at is not None
    assert result.creative_score == 0
    mock_analyze.assert_not_called()


@pytest.mark.asyncio
async def test_daily_creative_analysis_resets_failures(db, test_competitor):
    """Failed analyses (score=0) are reset and retried."""
    ad = Ad(competitor_id=test_competitor.id, ad_id="fail1", platform="facebook",
            creative_url="https://example.com/img.jpg",
            creative_analyzed_at=datetime.utcnow(), creative_score=0)
    db.add(ad)
    db.commit()

    mock_result = {
        "concept": "promo", "hook": "Test", "tone": "urgence",
        "text_overlay": "", "dominant_colors": [],
        "has_product": False, "has_face": False, "has_logo": False,
        "layout": "hero", "cta_style": "aucun", "score": 65,
        "tags": [], "summary": "Retry success",
        "product_category": "Autre", "product_subcategory": "",
        "ad_objective": "notoriété",
    }

    with patch("services.creative_analyzer.creative_analyzer.analyze_creative",
               new_callable=AsyncMock, return_value=mock_result):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)):
            await sched.daily_creative_analysis()

    result = db.query(Ad).filter(Ad.ad_id == "fail1").first()
    assert result.creative_score == 65
    assert result.creative_summary == "Retry success"


@pytest.mark.asyncio
async def test_daily_creative_analysis_no_ads(db, test_competitor):
    """No unanalyzed ads → no errors."""
    with patch("services.creative_analyzer.creative_analyzer.analyze_creative",
               new_callable=AsyncMock) as mock_analyze:
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)):
            await sched.daily_creative_analysis()

    mock_analyze.assert_not_called()

"""Tests for scheduled EU transparency enrichment."""
import json
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
async def test_enrich_transparency_processes_unenriched(db, test_competitor):
    """Scheduler enriches ads missing eu_total_reach with transparency data."""
    ad1 = Ad(competitor_id=test_competitor.id, ad_id="meta_ad_1", platform="facebook",
             eu_total_reach=None)
    ad2 = Ad(competitor_id=test_competitor.id, ad_id="meta_ad_2", platform="instagram",
             eu_total_reach=None)
    # Already enriched — should be skipped
    ad3 = Ad(competitor_id=test_competitor.id, ad_id="meta_ad_3", platform="facebook",
             eu_total_reach=5000)
    db.add_all([ad1, ad2, ad3])
    db.commit()

    mock_detail = {
        "success": True,
        "age_min": 18,
        "age_max": 65,
        "gender_audience": "ALL",
        "eu_total_reach": 12345,
        "location_audience": [{"name": "France", "type": "country"}],
        "age_country_gender_reach_breakdown": [
            {"country": "FR", "age_gender_breakdowns": [
                {"age_range": "25-34", "male": 3000, "female": 4000, "unknown": 100}
            ]}
        ],
        "byline": "Test Company",
        "payer": "Test Payer",
        "beneficiary": "Test Beneficiary",
    }

    mock_scrapecreators = MagicMock()
    mock_scrapecreators.get_facebook_ad_detail = AsyncMock(return_value=mock_detail)

    from services.scheduler import DataCollectionScheduler
    scheduler = DataCollectionScheduler.__new__(DataCollectionScheduler)

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)):
        with patch("services.scrapecreators.scrapecreators", mock_scrapecreators):
            await scheduler._enrich_transparency(db)

    db.refresh(ad1)
    db.refresh(ad2)
    db.refresh(ad3)

    # ad1 and ad2 should be enriched
    assert ad1.eu_total_reach == 12345
    assert ad1.age_min == 18
    assert ad1.gender_audience == "ALL"
    assert ad1.payer == "Test Payer"
    assert ad1.byline == "Test Company"
    breakdown = json.loads(ad1.age_country_gender_reach)
    assert breakdown[0]["country"] == "FR"

    assert ad2.eu_total_reach == 12345

    # ad3 was already enriched — not touched
    assert ad3.eu_total_reach == 5000


@pytest.mark.asyncio
async def test_enrich_transparency_handles_failures(db, test_competitor):
    """Failed enrichment sets eu_total_reach=0 so it's not retried."""
    ad1 = Ad(competitor_id=test_competitor.id, ad_id="fail_ad_1", platform="facebook",
             eu_total_reach=None)
    db.add(ad1)
    db.commit()

    mock_scrapecreators = MagicMock()
    mock_scrapecreators.get_facebook_ad_detail = AsyncMock(return_value={"success": False})

    from services.scheduler import DataCollectionScheduler
    scheduler = DataCollectionScheduler.__new__(DataCollectionScheduler)

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)):
        with patch("services.scrapecreators.scrapecreators", mock_scrapecreators):
            await scheduler._enrich_transparency(db)

    db.refresh(ad1)
    assert ad1.eu_total_reach == 0  # Marked as processed (won't be retried)
    assert ad1.age_country_gender_reach is None


@pytest.mark.asyncio
async def test_enrich_transparency_skips_non_meta(db, test_competitor):
    """Non-Meta ads (TikTok, Google) should not be enriched."""
    ad_tt = Ad(competitor_id=test_competitor.id, ad_id="tt_ad_1", platform="tiktok",
               eu_total_reach=None)
    ad_goog = Ad(competitor_id=test_competitor.id, ad_id="goog_ad_1", platform="google",
                 eu_total_reach=None)
    db.add_all([ad_tt, ad_goog])
    db.commit()

    mock_scrapecreators = MagicMock()
    mock_scrapecreators.get_facebook_ad_detail = AsyncMock(return_value={"success": True, "eu_total_reach": 999})

    from services.scheduler import DataCollectionScheduler
    scheduler = DataCollectionScheduler.__new__(DataCollectionScheduler)

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)):
        with patch("services.scrapecreators.scrapecreators", mock_scrapecreators):
            await scheduler._enrich_transparency(db)

    db.refresh(ad_tt)
    db.refresh(ad_goog)
    # Non-Meta ads should NOT be enriched
    assert ad_tt.eu_total_reach is None
    assert ad_goog.eu_total_reach is None
    mock_scrapecreators.get_facebook_ad_detail.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_transparency_noop_when_all_enriched(db, test_competitor):
    """No API calls when all ads already have transparency data."""
    ad1 = Ad(competitor_id=test_competitor.id, ad_id="done_1", platform="facebook",
             eu_total_reach=500)
    ad2 = Ad(competitor_id=test_competitor.id, ad_id="done_2", platform="instagram",
             eu_total_reach=0)
    db.add_all([ad1, ad2])
    db.commit()

    mock_scrapecreators = MagicMock()
    mock_scrapecreators.get_facebook_ad_detail = AsyncMock()

    from services.scheduler import DataCollectionScheduler
    scheduler = DataCollectionScheduler.__new__(DataCollectionScheduler)

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)):
        with patch("services.scrapecreators.scrapecreators", mock_scrapecreators):
            await scheduler._enrich_transparency(db)

    mock_scrapecreators.get_facebook_ad_detail.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_transparency_limits_to_100(db, test_competitor):
    """Max 100 ads per scheduler run to avoid API overload."""
    for i in range(150):
        db.add(Ad(competitor_id=test_competitor.id, ad_id=f"bulk_ad_{i}", platform="facebook",
                  eu_total_reach=None))
    db.commit()

    call_count = 0
    async def mock_detail(ad_id):
        nonlocal call_count
        call_count += 1
        return {"success": True, "eu_total_reach": 100}

    mock_scrapecreators = MagicMock()
    mock_scrapecreators.get_facebook_ad_detail = mock_detail

    from services.scheduler import DataCollectionScheduler
    scheduler = DataCollectionScheduler.__new__(DataCollectionScheduler)

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)):
        with patch("services.scrapecreators.scrapecreators", mock_scrapecreators):
            await scheduler._enrich_transparency(db)

    # Should process exactly 100 (the limit), not 150
    assert call_count == 100


@pytest.mark.asyncio
async def test_enrich_transparency_partial_data(db, test_competitor):
    """Enrichment works even when ScrapeCreators returns partial data."""
    ad1 = Ad(competitor_id=test_competitor.id, ad_id="partial_ad_1", platform="facebook",
             eu_total_reach=None)
    db.add(ad1)
    db.commit()

    # ScrapeCreators returns success but with minimal data
    mock_detail = {
        "success": True,
        "eu_total_reach": 500,
        # No age, gender, location, breakdown
    }

    mock_scrapecreators = MagicMock()
    mock_scrapecreators.get_facebook_ad_detail = AsyncMock(return_value=mock_detail)

    from services.scheduler import DataCollectionScheduler
    scheduler = DataCollectionScheduler.__new__(DataCollectionScheduler)

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)):
        with patch("services.scrapecreators.scrapecreators", mock_scrapecreators):
            await scheduler._enrich_transparency(db)

    db.refresh(ad1)
    assert ad1.eu_total_reach == 500
    assert ad1.age_min is None  # Not provided
    assert ad1.age_country_gender_reach is None  # Not provided

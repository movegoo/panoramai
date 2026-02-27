"""Tests for weekly GMB enrichment scheduler job."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

from database import Competitor, StoreLocation, Advertiser, UserAdvertiser, AdvertiserCompetitor


class NoCloseSession:
    """Wrapper that prevents close() from actually closing the session."""
    def __init__(self, real_db):
        self._db = real_db

    def __getattr__(self, name):
        if name == "close":
            return lambda: None  # no-op
        return getattr(self._db, name)


@pytest.mark.asyncio
async def test_weekly_gmb_enrichment_enriches_stores(db, test_competitor, test_advertiser):
    """Scheduler enriches BANCO stores that haven't been enriched recently."""
    # Create BANCO stores for the competitor
    store1 = StoreLocation(
        competitor_id=test_competitor.id, name="Store Paris", city="Paris",
        source="BANCO", latitude=48.8566, longitude=2.3522,
    )
    store2 = StoreLocation(
        competitor_id=test_competitor.id, name="Store Lyon", city="Lyon",
        source="BANCO", latitude=45.7640, longitude=4.8357,
    )
    # Already enriched recently — should be skipped
    store3 = StoreLocation(
        competitor_id=test_competitor.id, name="Store Marseille", city="Marseille",
        source="BANCO", latitude=43.2965, longitude=5.3698,
        google_rating=4.2, rating_fetched_at=datetime.utcnow(),
    )
    db.add_all([store1, store2, store3])
    db.commit()

    mock_result = {
        "success": True,
        "rating": 4.5,
        "reviews_count": 120,
        "place_id": "ChIJ123",
        "phone": "+33 1 23 45 67 89",
        "website": "https://example.com",
        "type": "Supermarché",
        "thumbnail": "https://img.example.com/thumb.jpg",
        "open_state": "Open",
        "hours": '{"monday":"9-20"}',
        "price": "$$",
    }

    mock_gmb = MagicMock()
    mock_gmb.is_configured = True
    mock_gmb.enrich_store = AsyncMock(return_value=mock_result)

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch("services.gmb_service.gmb_service", mock_gmb), \
         patch("services.scheduler.DataCollectionScheduler.weekly_gmb_enrichment.__module__", create=True):

        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()

        # Patch the gmb_service import inside the method
        with patch.dict("sys.modules", {"services.gmb_service": MagicMock(gmb_service=mock_gmb)}):
            await sched.weekly_gmb_enrichment()

    # store1 and store2 should be enriched, store3 should be untouched
    db.refresh(store1)
    db.refresh(store2)
    db.refresh(store3)

    assert store1.google_rating == 4.5
    assert store1.google_reviews_count == 120
    assert store1.google_phone == "+33 1 23 45 67 89"
    assert store1.google_website == "https://example.com"
    assert store1.google_type == "Supermarché"
    assert store1.google_thumbnail == "https://img.example.com/thumb.jpg"
    assert store1.google_open_state == "Open"
    assert store1.google_price == "$$"
    assert store1.gmb_score is not None
    assert store1.rating_fetched_at is not None

    assert store2.google_rating == 4.5
    assert store2.gmb_score is not None

    # store3 was recently enriched — should keep its original rating
    assert store3.google_rating == 4.2

    # enrich_store should have been called exactly 2 times
    assert mock_gmb.enrich_store.call_count == 2


@pytest.mark.asyncio
async def test_weekly_gmb_enrichment_skips_when_not_configured(db, test_competitor, test_advertiser):
    """Scheduler skips GMB enrichment when service is not configured."""
    store = StoreLocation(
        competitor_id=test_competitor.id, name="Store Test", city="Paris",
        source="BANCO",
    )
    db.add(store)
    db.commit()

    mock_gmb = MagicMock()
    mock_gmb.is_configured = False

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": MagicMock(gmb_service=mock_gmb)}):

        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    db.refresh(store)
    assert store.google_rating is None  # Not enriched


@pytest.mark.asyncio
async def test_weekly_gmb_enrichment_handles_errors(db, test_competitor, test_advertiser):
    """Scheduler handles API errors gracefully without crashing."""
    store = StoreLocation(
        competitor_id=test_competitor.id, name="Store Error", city="Paris",
        source="BANCO",
    )
    db.add(store)
    db.commit()

    mock_gmb = MagicMock()
    mock_gmb.is_configured = True
    mock_gmb.enrich_store = AsyncMock(return_value={"success": False, "error": "API limit reached"})

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": MagicMock(gmb_service=mock_gmb)}):

        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    db.refresh(store)
    assert store.google_rating is None  # Not enriched due to error


@pytest.mark.asyncio
async def test_weekly_gmb_re_enriches_old_stores(db, test_competitor, test_advertiser):
    """Scheduler re-enriches stores whose data is older than 30 days."""
    old_date = datetime.utcnow() - timedelta(days=35)
    store = StoreLocation(
        competitor_id=test_competitor.id, name="Store Old", city="Paris",
        source="BANCO", google_rating=3.5, rating_fetched_at=old_date,
    )
    db.add(store)
    db.commit()

    mock_result = {
        "success": True, "rating": 4.0, "reviews_count": 200,
        "place_id": "ChIJold", "phone": None, "website": None,
        "type": None, "thumbnail": None, "open_state": None,
        "hours": None, "price": None,
    }

    mock_gmb = MagicMock()
    mock_gmb.is_configured = True
    mock_gmb.enrich_store = AsyncMock(return_value=mock_result)

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": MagicMock(gmb_service=mock_gmb)}):

        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    db.refresh(store)
    assert store.google_rating == 4.0  # Updated from 3.5
    assert store.google_reviews_count == 200

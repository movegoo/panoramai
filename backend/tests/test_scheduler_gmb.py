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


def _make_mock_gmb(configured=True, result=None):
    """Helper to build a mock gmb_service + compute_gmb_score module."""
    mock_gmb = MagicMock()
    mock_gmb.is_configured = configured
    if result is not None:
        mock_gmb.enrich_store = AsyncMock(return_value=result)
    mock_module = MagicMock(gmb_service=mock_gmb)
    # Expose the real compute_gmb_score so scores are actually computed
    from services.gmb_service import compute_gmb_score
    mock_module.compute_gmb_score = compute_gmb_score
    return mock_gmb, mock_module


def _success_result(**overrides):
    """Default successful enrichment result."""
    base = {
        "success": True, "rating": 4.5, "reviews_count": 120,
        "place_id": "ChIJ123", "phone": "+33 1 23 45 67 89",
        "website": "https://example.com", "type": "Supermarché",
        "thumbnail": "https://img.example.com/thumb.jpg",
        "open_state": "Open", "hours": '{"monday":"9-20"}', "price": "$$",
    }
    base.update(overrides)
    return base


# ── Core enrichment ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_weekly_gmb_enrichment_enriches_stores(db, test_competitor, test_advertiser):
    """Scheduler enriches BANCO stores that haven't been enriched recently."""
    store1 = StoreLocation(
        competitor_id=test_competitor.id, name="Store Paris", city="Paris",
        source="BANCO", latitude=48.8566, longitude=2.3522,
    )
    store2 = StoreLocation(
        competitor_id=test_competitor.id, name="Store Lyon", city="Lyon",
        source="BANCO", latitude=45.7640, longitude=4.8357,
    )
    # Already enriched recently — should be skipped by the query filter
    store3 = StoreLocation(
        competitor_id=test_competitor.id, name="Store Marseille", city="Marseille",
        source="BANCO", latitude=43.2965, longitude=5.3698,
        google_rating=4.2, rating_fetched_at=datetime.utcnow(),
    )
    db.add_all([store1, store2, store3])
    db.commit()

    mock_gmb, mock_module = _make_mock_gmb(result=_success_result())

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    db.refresh(store1)
    db.refresh(store2)
    db.refresh(store3)

    # store1 & store2 enriched
    assert store1.google_rating == 4.5
    assert store1.google_reviews_count == 120
    assert store1.google_phone == "+33 1 23 45 67 89"
    assert store1.google_website == "https://example.com"
    assert store1.google_type == "Supermarché"
    assert store1.google_thumbnail == "https://img.example.com/thumb.jpg"
    assert store1.google_open_state == "Open"
    assert store1.google_price == "$$"
    assert store1.gmb_score is not None
    assert store1.gmb_score > 0
    assert store1.rating_fetched_at is not None

    assert store2.google_rating == 4.5
    assert store2.gmb_score is not None

    # store3 untouched
    assert store3.google_rating == 4.2

    assert mock_gmb.enrich_store.call_count == 2


# ── Skip / early-exit paths ────────────────────────────────────────

@pytest.mark.asyncio
async def test_skips_when_not_configured(db, test_competitor, test_advertiser):
    """Scheduler skips GMB enrichment when service is not configured."""
    store = StoreLocation(
        competitor_id=test_competitor.id, name="Store Test", city="Paris",
        source="BANCO",
    )
    db.add(store)
    db.commit()

    mock_gmb, mock_module = _make_mock_gmb(configured=False)

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    db.refresh(store)
    assert store.google_rating is None


@pytest.mark.asyncio
async def test_skips_when_no_advertisers(db):
    """Scheduler exits early when no active advertisers exist."""
    mock_gmb, mock_module = _make_mock_gmb()

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        # Should not raise — just return early
        await sched.weekly_gmb_enrichment()

    mock_gmb.enrich_store.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_no_competitors(db, test_advertiser):
    """Scheduler exits early when advertisers have no linked competitors."""
    mock_gmb, mock_module = _make_mock_gmb()

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    mock_gmb.enrich_store.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_all_stores_recently_enriched(db, test_competitor, test_advertiser):
    """Scheduler exits early when all BANCO stores are recently enriched."""
    store = StoreLocation(
        competitor_id=test_competitor.id, name="Fresh Store", city="Paris",
        source="BANCO", google_rating=4.0, rating_fetched_at=datetime.utcnow(),
    )
    db.add(store)
    db.commit()

    mock_gmb, mock_module = _make_mock_gmb()

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    mock_gmb.enrich_store.assert_not_called()


# ── Error handling ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handles_api_failure(db, test_competitor, test_advertiser):
    """Scheduler handles API errors gracefully without crashing."""
    store = StoreLocation(
        competitor_id=test_competitor.id, name="Store Error", city="Paris",
        source="BANCO",
    )
    db.add(store)
    db.commit()

    mock_gmb, mock_module = _make_mock_gmb(
        result={"success": False, "error": "API limit reached"},
    )

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    db.refresh(store)
    assert store.google_rating is None


@pytest.mark.asyncio
async def test_handles_enrich_store_exception(db, test_competitor, test_advertiser):
    """Scheduler catches exceptions from enrich_store and continues."""
    store1 = StoreLocation(
        competitor_id=test_competitor.id, name="Store Crash", city="Paris",
        source="BANCO",
    )
    store2 = StoreLocation(
        competitor_id=test_competitor.id, name="Store OK", city="Lyon",
        source="BANCO",
    )
    db.add_all([store1, store2])
    db.commit()

    call_count = 0

    async def _side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Network timeout")
        return _success_result()

    mock_gmb, mock_module = _make_mock_gmb()
    mock_gmb.enrich_store = AsyncMock(side_effect=_side_effect)

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    db.refresh(store1)
    db.refresh(store2)

    # store1 failed, store2 succeeded
    assert store1.google_rating is None
    assert store2.google_rating == 4.5
    assert store2.gmb_score is not None


@pytest.mark.asyncio
async def test_handles_compute_gmb_score_exception(db, test_competitor, test_advertiser):
    """If compute_gmb_score raises, store is still enriched with gmb_score=None."""
    store = StoreLocation(
        competitor_id=test_competitor.id, name="Store Score Crash", city="Paris",
        source="BANCO",
    )
    db.add(store)
    db.commit()

    def _broken_score(**kwargs):
        raise TypeError("unexpected None")

    mock_gmb = MagicMock()
    mock_gmb.is_configured = True
    mock_gmb.enrich_store = AsyncMock(return_value=_success_result())
    mock_module = MagicMock(gmb_service=mock_gmb, compute_gmb_score=_broken_score)

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    db.refresh(store)
    # Rating fields still saved, but gmb_score is None due to error
    assert store.google_rating == 4.5
    assert store.google_phone == "+33 1 23 45 67 89"
    assert store.gmb_score is None
    assert store.rating_fetched_at is not None


# ── Mixed success / failure ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_mixed_success_and_failure_commits_successful(db, test_competitor, test_advertiser):
    """With mixed results, successful enrichments are committed despite errors."""
    stores = [
        StoreLocation(
            competitor_id=test_competitor.id, name=f"Store {i}", city=f"City {i}",
            source="BANCO",
        )
        for i in range(4)
    ]
    db.add_all(stores)
    db.commit()

    call_idx = 0

    async def _alternating(**kwargs):
        nonlocal call_idx
        call_idx += 1
        if call_idx % 2 == 0:
            return {"success": False, "error": "Quota exceeded"}
        return _success_result()

    mock_gmb, mock_module = _make_mock_gmb()
    mock_gmb.enrich_store = AsyncMock(side_effect=_alternating)

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    for s in stores:
        db.refresh(s)

    enriched_count = sum(1 for s in stores if s.google_rating is not None)
    assert enriched_count == 2  # Half succeeded


# ── Re-enrichment ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_re_enriches_old_stores(db, test_competitor, test_advertiser):
    """Scheduler re-enriches stores whose data is older than 30 days."""
    old_date = datetime.utcnow() - timedelta(days=35)
    store = StoreLocation(
        competitor_id=test_competitor.id, name="Store Old", city="Paris",
        source="BANCO", google_rating=3.5, rating_fetched_at=old_date,
    )
    db.add(store)
    db.commit()

    mock_gmb, mock_module = _make_mock_gmb(result=_success_result(rating=4.0, reviews_count=200))

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    db.refresh(store)
    assert store.google_rating == 4.0  # Updated from 3.5
    assert store.google_reviews_count == 200


@pytest.mark.asyncio
async def test_does_not_re_enrich_29_day_old_stores(db, test_competitor, test_advertiser):
    """Stores enriched 29 days ago should NOT be re-enriched (< 30 day cutoff)."""
    recent_date = datetime.utcnow() - timedelta(days=29)
    store = StoreLocation(
        competitor_id=test_competitor.id, name="Store Recent", city="Paris",
        source="BANCO", google_rating=3.8, rating_fetched_at=recent_date,
    )
    db.add(store)
    db.commit()

    mock_gmb, mock_module = _make_mock_gmb()

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    db.refresh(store)
    assert store.google_rating == 3.8  # Unchanged
    mock_gmb.enrich_store.assert_not_called()


# ── Edge cases ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_skips_non_banco_stores(db, test_competitor, test_advertiser):
    """Scheduler only enriches BANCO stores, not other sources."""
    banco_store = StoreLocation(
        competitor_id=test_competitor.id, name="BANCO Store", city="Paris",
        source="BANCO",
    )
    other_store = StoreLocation(
        competitor_id=test_competitor.id, name="Manual Store", city="Paris",
        source="manual",
    )
    db.add_all([banco_store, other_store])
    db.commit()

    mock_gmb, mock_module = _make_mock_gmb(result=_success_result())

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    db.refresh(banco_store)
    db.refresh(other_store)

    assert banco_store.google_rating == 4.5
    assert other_store.google_rating is None
    assert mock_gmb.enrich_store.call_count == 1


@pytest.mark.asyncio
async def test_stores_with_null_coordinates(db, test_competitor, test_advertiser):
    """Stores with null lat/lon should still be passed to enrich_store."""
    store = StoreLocation(
        competitor_id=test_competitor.id, name="No Coords Store", city="Paris",
        source="BANCO", latitude=None, longitude=None,
    )
    db.add(store)
    db.commit()

    mock_gmb, mock_module = _make_mock_gmb(result=_success_result())

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    db.refresh(store)
    assert store.google_rating == 4.5

    # Verify None was passed for coordinates
    call_kwargs = mock_gmb.enrich_store.call_args[1]
    assert call_kwargs["latitude"] is None
    assert call_kwargs["longitude"] is None


@pytest.mark.asyncio
async def test_enrichment_with_all_null_extended_fields(db, test_competitor, test_advertiser):
    """Enrichment with success but all extended fields null."""
    store = StoreLocation(
        competitor_id=test_competitor.id, name="Minimal Store", city="Paris",
        source="BANCO",
    )
    db.add(store)
    db.commit()

    result = _success_result(
        phone=None, website=None, type=None, thumbnail=None,
        open_state=None, hours=None, price=None,
    )
    mock_gmb, mock_module = _make_mock_gmb(result=result)

    with patch("services.scheduler.SessionLocal", return_value=NoCloseSession(db)), \
         patch.dict("sys.modules", {"services.gmb_service": mock_module}):
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        await sched.weekly_gmb_enrichment()

    db.refresh(store)
    assert store.google_rating == 4.5
    assert store.google_phone is None
    assert store.google_website is None
    assert store.gmb_score is not None  # compute_gmb_score handles None fields


# ── Manual endpoint ─────────────────────────────────────────────────

def test_run_gmb_endpoint_returns_202(client):
    """POST /api/scheduler/run-gmb returns success message."""
    resp = client.post("/api/scheduler/run-gmb")
    assert resp.status_code == 200
    data = resp.json()
    assert "GMB" in data["message"]
    assert "timestamp" in data

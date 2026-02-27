"""Tests for extended GMB fields in gmb-scoring endpoint."""
import pytest
from datetime import datetime

from database import Competitor, StoreLocation, AdvertiserCompetitor


def _make_store(db, competitor_id, i, **overrides):
    """Helper to create a StoreLocation with default GMB data."""
    defaults = dict(
        competitor_id=competitor_id,
        name=f"Store {i}",
        city=f"City {i}",
        source="BANCO",
        latitude=48.8 + i * 0.1,
        longitude=2.3 + i * 0.1,
        google_rating=4.5 - i * 0.2,
        google_reviews_count=200 - i * 30,
        gmb_score=90 - i * 10,
        rating_fetched_at=datetime.utcnow(),
    )
    defaults.update(overrides)
    store = StoreLocation(**defaults)
    db.add(store)
    return store


# ── Extended fields present ─────────────────────────────────────────

def test_gmb_scoring_returns_extended_fields(client, auth_headers, db, test_competitor, test_advertiser):
    """Top stores include all 7 extended GMB fields."""
    for i in range(5):
        _make_store(db, test_competitor.id, i,
            google_phone=f"+33 1 00 00 00 0{i}",
            google_website=f"https://store{i}.example.com",
            google_type="Supermarché",
            google_thumbnail=f"https://img.example.com/thumb{i}.jpg",
            google_open_state="Open" if i < 3 else "Closed",
            google_hours='{"monday":"9-20"}',
            google_price="$$",
            google_place_id=f"ChIJ{i}",
        )
    db.commit()

    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["competitors"]) > 0
    comp = data["competitors"][0]
    assert len(comp["top_stores"]) > 0

    top = comp["top_stores"][0]

    # All 7 extended fields present
    for field in ("phone", "website", "open_state", "thumbnail", "hours", "price", "type"):
        assert field in top, f"Missing field: {field}"

    # Values are correct (top store = highest gmb_score = index 0)
    assert top["phone"] is not None
    assert top["website"] is not None
    assert top["open_state"] == "Open"
    assert top["thumbnail"] is not None
    assert top["price"] == "$$"
    assert top["type"] == "Supermarché"


# ── Nullable fields ─────────────────────────────────────────────────

def test_extended_fields_nullable(client, auth_headers, db, test_competitor, test_advertiser):
    """Extended fields are null when store is not fully enriched."""
    _make_store(db, test_competitor.id, 0,
        google_phone=None, google_website=None, google_type=None,
        google_thumbnail=None, google_open_state=None,
        google_hours=None, google_price=None,
    )
    db.commit()

    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200

    comp = resp.json()["competitors"][0]
    top = comp["top_stores"][0]

    assert top["phone"] is None
    assert top["website"] is None
    assert top["open_state"] is None
    assert top["thumbnail"] is None
    assert top["hours"] is None
    assert top["price"] is None
    assert top["type"] is None


# ── Flop stores ─────────────────────────────────────────────────────

def test_flop_stores_have_extended_fields(client, auth_headers, db, test_competitor, test_advertiser):
    """Flop stores also return extended GMB fields (needs >3 scored stores)."""
    for i in range(5):
        _make_store(db, test_competitor.id, i,
            google_phone=f"+33 {i}",
            google_website=f"https://s{i}.com",
            google_type="Magasin",
            google_open_state="Open",
        )
    db.commit()

    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200

    comp = resp.json()["competitors"][0]
    assert len(comp["flop_stores"]) > 0

    flop = comp["flop_stores"][0]
    assert "phone" in flop
    assert "website" in flop
    assert "type" in flop
    assert flop["phone"] is not None


def test_flop_stores_empty_with_3_or_fewer_stores(client, auth_headers, db, test_competitor, test_advertiser):
    """Flop stores list is empty when there are 3 or fewer scored stores."""
    for i in range(3):
        _make_store(db, test_competitor.id, i)
    db.commit()

    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200

    comp = resp.json()["competitors"][0]
    assert comp["flop_stores"] == []


def test_flop_stores_populated_with_4_stores(client, auth_headers, db, test_competitor, test_advertiser):
    """Flop stores list is populated when there are 4+ scored stores."""
    for i in range(4):
        _make_store(db, test_competitor.id, i,
            google_phone=f"+33 {i}",
        )
    db.commit()

    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200

    comp = resp.json()["competitors"][0]
    assert len(comp["flop_stores"]) > 0
    # Flop stores should have extended fields
    assert "phone" in comp["flop_stores"][0]


# ── Edge case: all stores have gmb_score = None ─────────────────────

def test_all_stores_null_gmb_score(client, auth_headers, db, test_competitor, test_advertiser):
    """Endpoint handles competitors where all stores have gmb_score=None."""
    for i in range(3):
        _make_store(db, test_competitor.id, i,
            gmb_score=None, google_rating=None, google_reviews_count=None,
        )
    db.commit()

    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200

    comp = resp.json()["competitors"][0]
    # No scored stores → top_stores and flop_stores empty
    assert comp["top_stores"] == []
    assert comp["flop_stores"] == []
    assert comp["avg_score"] is None


# ── Edge case: single store ─────────────────────────────────────────

def test_single_store(client, auth_headers, db, test_competitor, test_advertiser):
    """Endpoint works with a single scored store."""
    _make_store(db, test_competitor.id, 0,
        google_phone="+33 1 00 00 00 00",
        google_website="https://single.com",
        google_type="Restaurant",
    )
    db.commit()

    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200

    comp = resp.json()["competitors"][0]
    assert len(comp["top_stores"]) == 1
    assert comp["flop_stores"] == []  # < 4 stores
    assert comp["top_stores"][0]["phone"] == "+33 1 00 00 00 00"
    assert comp["top_stores"][0]["type"] == "Restaurant"


# ── Edge case: no stores at all ─────────────────────────────────────

def test_no_stores(client, auth_headers, db, test_competitor, test_advertiser):
    """Endpoint handles competitor with 0 BANCO stores — competitor excluded from results."""
    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    # Competitor has 0 BANCO stores → not included in gmb-scoring results
    # (the endpoint only processes competitors with BANCO store_locations)
    assert data["competitors"] == []
    assert data["market_avg_score"] == 0


# ── Edge case: no competitors ───────────────────────────────────────

def test_no_competitors_returns_empty(client, auth_headers, db, test_advertiser):
    """Endpoint returns empty competitors list when no competitors linked."""
    # Remove competitor links
    db.query(AdvertiserCompetitor).delete()
    db.commit()

    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert data["competitors"] == []
    assert data["market_avg_score"] == 0


# ── Top stores order ────────────────────────────────────────────────

def test_top_stores_ordered_by_score_desc(client, auth_headers, db, test_competitor, test_advertiser):
    """Top stores are ordered by gmb_score descending."""
    scores = [50, 90, 30, 70, 80]
    for i, score in enumerate(scores):
        _make_store(db, test_competitor.id, i, gmb_score=score)
    db.commit()

    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200

    comp = resp.json()["competitors"][0]
    top_scores = [s["gmb_score"] for s in comp["top_stores"]]
    assert top_scores == [90, 80, 70]  # Top 3 descending


# ── Market averages ─────────────────────────────────────────────────

def test_market_averages_computed_correctly(client, auth_headers, db, test_competitor, test_advertiser):
    """Market average score and rating are computed across all competitors."""
    for i in range(3):
        _make_store(db, test_competitor.id, i,
            gmb_score=60 + i * 10,  # 60, 70, 80
            google_rating=3.0 + i * 0.5,  # 3.0, 3.5, 4.0
            google_reviews_count=100 + i * 50,  # 100, 150, 200
        )
    db.commit()

    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert data["market_avg_score"] == 70.0  # (60+70+80)/3
    assert data["market_avg_rating"] == 3.5  # (3.0+3.5+4.0)/3
    assert data["total_reviews"] == 450  # 100+150+200

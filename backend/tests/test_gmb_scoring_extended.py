"""Tests for extended GMB fields in gmb-scoring endpoint."""
import pytest
from datetime import datetime

from database import Competitor, StoreLocation, AdvertiserCompetitor


@pytest.fixture
def stores_with_gmb(db, test_competitor, test_advertiser):
    """Create stores with full GMB data."""
    stores = [
        StoreLocation(
            competitor_id=test_competitor.id, name=f"Store {i}", city=f"City {i}",
            source="BANCO", latitude=48.8 + i * 0.1, longitude=2.3 + i * 0.1,
            google_rating=4.5 - i * 0.3,
            google_reviews_count=100 + i * 50,
            google_place_id=f"ChIJ{i}",
            google_phone=f"+33 1 00 00 00 0{i}",
            google_website=f"https://store{i}.example.com",
            google_type="Supermarché",
            google_thumbnail=f"https://img.example.com/thumb{i}.jpg",
            google_open_state="Open" if i < 3 else "Closed",
            google_hours='{"monday":"9-20"}',
            google_price="$$",
            gmb_score=90 - i * 10,
            rating_fetched_at=datetime.utcnow(),
        )
        for i in range(5)
    ]
    db.add_all(stores)
    db.commit()
    return stores


def test_gmb_scoring_returns_extended_fields(client, auth_headers, stores_with_gmb):
    """The gmb-scoring endpoint returns extended GMB fields in top/flop stores."""
    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "competitors" in data
    assert len(data["competitors"]) > 0

    comp = data["competitors"][0]
    assert "top_stores" in comp
    assert len(comp["top_stores"]) > 0

    top = comp["top_stores"][0]
    # Standard fields
    assert "id" in top
    assert "name" in top
    assert "city" in top
    assert "rating" in top
    assert "reviews_count" in top
    assert "gmb_score" in top
    assert "place_id" in top

    # Extended fields
    assert "phone" in top
    assert "website" in top
    assert "open_state" in top
    assert "thumbnail" in top
    assert "hours" in top
    assert "price" in top
    assert "type" in top

    # Verify actual values
    assert top["phone"] is not None
    assert top["website"] is not None
    assert top["open_state"] == "Open"
    assert top["thumbnail"] is not None
    assert top["price"] == "$$"
    assert top["type"] == "Supermarché"


def test_gmb_scoring_extended_fields_nullable(client, auth_headers, db, test_competitor, test_advertiser):
    """Extended fields are null when not enriched."""
    store = StoreLocation(
        competitor_id=test_competitor.id, name="Bare Store", city="Paris",
        source="BANCO", google_rating=4.0, google_reviews_count=50,
        gmb_score=60, rating_fetched_at=datetime.utcnow(),
    )
    db.add(store)
    db.commit()

    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    comp = data["competitors"][0]
    top = comp["top_stores"][0]

    assert top["phone"] is None
    assert top["website"] is None
    assert top["open_state"] is None
    assert top["thumbnail"] is None
    assert top["hours"] is None
    assert top["price"] is None
    assert top["type"] is None


def test_gmb_scoring_flop_stores_have_extended_fields(client, auth_headers, db, test_competitor, test_advertiser):
    """Flop stores also return extended GMB fields when enough stores exist."""
    # Need > 3 stores for flop_stores to be populated
    stores = [
        StoreLocation(
            competitor_id=test_competitor.id, name=f"Store {i}", city=f"City {i}",
            source="BANCO", google_rating=4.5 - i * 0.2,
            google_reviews_count=100 - i * 10,
            gmb_score=90 - i * 15,
            google_phone=f"+33 {i}",
            google_website=f"https://s{i}.com",
            google_open_state="Open",
            google_type="Magasin",
            rating_fetched_at=datetime.utcnow(),
        )
        for i in range(5)
    ]
    db.add_all(stores)
    db.commit()

    resp = client.get("/api/geo/gmb-scoring", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    comp = data["competitors"][0]
    if comp.get("flop_stores"):
        flop = comp["flop_stores"][0]
        assert "phone" in flop
        assert "website" in flop
        assert "type" in flop

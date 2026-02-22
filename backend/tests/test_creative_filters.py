"""Tests for creative analysis filters and enriched fields."""
import json
from datetime import datetime

import pytest

from database import Ad, Competitor, AdvertiserCompetitor
from services.creative_analyzer import CreativeAnalyzer


# ── Model / column tests ─────────────────────────────────────

def test_ad_new_columns_exist(db, test_competitor):
    """New enriched fields can be stored on the Ad model."""
    ad = Ad(
        competitor_id=test_competitor.id,
        ad_id="test-promo-001",
        platform="facebook",
        is_active=True,
        creative_analyzed_at=datetime.utcnow(),
        creative_score=72,
        product_category="Épicerie",
        promo_type="prix-barré",
        creative_format="catalogue",
        price_visible=True,
        price_value="2,99€",
        seasonal_event="soldes",
    )
    db.add(ad)
    db.commit()
    db.refresh(ad)

    assert ad.promo_type == "prix-barré"
    assert ad.creative_format == "catalogue"
    assert ad.price_visible is True
    assert ad.price_value == "2,99€"
    assert ad.seasonal_event == "soldes"


def test_ad_new_columns_nullable(db, test_competitor):
    """New columns default to None when not set."""
    ad = Ad(
        competitor_id=test_competitor.id,
        ad_id="test-null-001",
        platform="facebook",
        is_active=True,
    )
    db.add(ad)
    db.commit()
    db.refresh(ad)

    assert ad.promo_type is None
    assert ad.creative_format is None
    assert ad.price_visible is None
    assert ad.price_value is None
    assert ad.seasonal_event is None


# ── Prompt parsing tests ─────────────────────────────────────

class TestPromptParsing:
    """Test that CreativeAnalyzer._parse_analysis handles new fields."""

    def setup_method(self):
        self.analyzer = CreativeAnalyzer()

    def test_parse_new_fields(self):
        raw = json.dumps({
            "concept": "promo",
            "hook": "Prix cassé",
            "tone": "urgence",
            "text_overlay": "-30%",
            "dominant_colors": ["#FF0000"],
            "has_product": True,
            "has_face": False,
            "has_logo": True,
            "has_price": True,
            "layout": "image-unique",
            "cta_style": "bouton",
            "score": 85,
            "tags": ["promo", "soldes"],
            "summary": "Promo agressive",
            "product_category": "Épicerie",
            "product_subcategory": "Café",
            "ad_objective": "conversion",
            "promo_type": "pourcentage",
            "creative_format": "multi-produits",
            "price_visible": True,
            "price_value": "4,99€",
            "seasonal_event": "soldes",
        })
        result = self.analyzer._parse_analysis(raw)
        assert result is not None
        assert result["promo_type"] == "pourcentage"
        assert result["creative_format"] == "multi-produits"
        assert result["price_visible"] is True
        assert result["price_value"] == "4,99€"
        assert result["seasonal_event"] == "soldes"

    def test_parse_missing_new_fields_defaults(self):
        raw = json.dumps({
            "concept": "lifestyle",
            "hook": "Découvrez",
            "tone": "aspiration",
            "text_overlay": "",
            "dominant_colors": [],
            "has_product": False,
            "has_face": True,
            "has_logo": False,
            "has_price": False,
            "layout": "plein-écran",
            "cta_style": "aucun",
            "score": 60,
            "tags": [],
            "summary": "Lifestyle shot",
            "product_category": "Corporate & RSE",
            "product_subcategory": "",
            "ad_objective": "notoriété",
        })
        result = self.analyzer._parse_analysis(raw)
        assert result is not None
        assert result["promo_type"] == ""
        assert result["creative_format"] == ""
        assert result["price_visible"] is False
        assert result["price_value"] == ""
        assert result["seasonal_event"] == ""


# ── Insights endpoint filter tests ───────────────────────────

def _create_test_ads(db, test_competitor, test_advertiser):
    """Create test ads with various categories/locations for filter testing."""
    comp2 = Competitor(name="Lidl", website="https://lidl.fr", is_active=True)
    db.add(comp2)
    db.commit()
    db.refresh(comp2)
    link2 = AdvertiserCompetitor(advertiser_id=test_advertiser.id, competitor_id=comp2.id)
    db.add(link2)
    db.commit()

    ads = [
        Ad(
            competitor_id=test_competitor.id,
            ad_id="cf-001",
            platform="facebook",
            is_active=True,
            creative_analyzed_at=datetime.utcnow(),
            creative_score=80,
            creative_concept="promo",
            creative_tone="urgence",
            product_category="Épicerie",
            promo_type="prix-barré",
            creative_format="catalogue",
            seasonal_event="soldes",
            location_audience=json.dumps([{"name": "France", "type": "country"}, {"name": "Île-de-France", "type": "region"}]),
        ),
        Ad(
            competitor_id=test_competitor.id,
            ad_id="cf-002",
            platform="facebook",
            is_active=True,
            creative_analyzed_at=datetime.utcnow(),
            creative_score=65,
            creative_concept="lifestyle",
            creative_tone="aspiration",
            product_category="Textile & Mode",
            promo_type="aucune",
            creative_format="ambiance",
            seasonal_event="aucun",
            location_audience=json.dumps([{"name": "France", "type": "country"}]),
        ),
        Ad(
            competitor_id=comp2.id,
            ad_id="li-001",
            platform="facebook",
            is_active=True,
            creative_analyzed_at=datetime.utcnow(),
            creative_score=70,
            creative_concept="promo",
            creative_tone="bon-plan",
            product_category="Épicerie",
            promo_type="lot",
            creative_format="multi-produits",
            seasonal_event="aucun",
            location_audience=json.dumps([{"name": "France", "type": "country"}, {"name": "Île-de-France", "type": "region"}]),
        ),
    ]
    db.add_all(ads)
    db.commit()
    return comp2


def test_insights_no_filter(client, db, test_competitor, test_advertiser, adv_headers):
    """Insights without filters returns all analyzed ads."""
    _create_test_ads(db, test_competitor, test_advertiser)
    resp = client.get("/api/creative/insights", headers=adv_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 3
    assert len(data["promo_types"]) > 0
    assert len(data["creative_formats"]) > 0


def test_insights_filter_competitor(client, db, test_competitor, test_advertiser, adv_headers):
    """Insights filtered by competitor_id returns only that competitor's ads."""
    _create_test_ads(db, test_competitor, test_advertiser)
    resp = client.get(f"/api/creative/insights?competitor_id={test_competitor.id}", headers=adv_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 2
    # All should be from Carrefour
    for comp in data["by_competitor"]:
        assert comp["competitor"] == "Carrefour"


def test_insights_filter_category(client, db, test_competitor, test_advertiser, adv_headers):
    """Insights filtered by category returns matching ads."""
    _create_test_ads(db, test_competitor, test_advertiser)
    resp = client.get("/api/creative/insights?category=Épicerie", headers=adv_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 2


def test_insights_filter_location(client, db, test_competitor, test_advertiser, adv_headers):
    """Insights filtered by location returns matching ads."""
    _create_test_ads(db, test_competitor, test_advertiser)
    resp = client.get("/api/creative/insights?location=Île-de-France", headers=adv_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 2


def test_insights_combined_filters(client, db, test_competitor, test_advertiser, adv_headers):
    """Insights with combined competitor + category filters."""
    _create_test_ads(db, test_competitor, test_advertiser)
    resp = client.get(
        f"/api/creative/insights?competitor_id={test_competitor.id}&category=Épicerie",
        headers=adv_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 1


def test_insights_seasonal_distribution(client, db, test_competitor, test_advertiser, adv_headers):
    """Insights include seasonal_events distribution."""
    _create_test_ads(db, test_competitor, test_advertiser)
    resp = client.get("/api/creative/insights", headers=adv_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "seasonal_events" in data
    # Only "soldes" should appear (aucun is excluded)
    if data["seasonal_events"]:
        assert data["seasonal_events"][0]["seasonal_event"] == "soldes"

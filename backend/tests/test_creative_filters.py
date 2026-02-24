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

class TestMediaTypeDetection:
    """Test magic byte detection for image MIME types."""

    def test_detect_png(self):
        png_header = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        assert CreativeAnalyzer._detect_media_type(png_header) == "image/png"

    def test_detect_jpeg(self):
        jpeg_header = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        assert CreativeAnalyzer._detect_media_type(jpeg_header) == "image/jpeg"

    def test_detect_webp(self):
        webp_header = b'RIFF\x00\x00\x00\x00WEBP' + b'\x00' * 100
        assert CreativeAnalyzer._detect_media_type(webp_header) == "image/webp"

    def test_detect_gif(self):
        gif_header = b'GIF89a' + b'\x00' * 100
        assert CreativeAnalyzer._detect_media_type(gif_header) == "image/gif"

    def test_detect_unknown(self):
        assert CreativeAnalyzer._detect_media_type(b'\x00\x00\x00') == ""


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

    def test_text_only_analysis_method_exists(self):
        """CreativeAnalyzer has analyze_text_only method for Google Ads."""
        assert hasattr(self.analyzer, "analyze_text_only")
        assert callable(self.analyzer.analyze_text_only)

    def test_gemini_key_property(self):
        """CreativeAnalyzer has gemini_key and mistral_key properties."""
        assert hasattr(self.analyzer, "gemini_key")
        assert hasattr(self.analyzer, "mistral_key")

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


# ── Fusion logic tests ────────────────────────────────────────

class TestTextFusion:
    """Test double-analysis fusion logic."""

    def setup_method(self):
        self.analyzer = CreativeAnalyzer()

    def test_fuse_both_agree(self):
        """When both models agree, result matches."""
        g = {"concept": "promo", "tone": "urgence", "score": 80, "tags": ["soldes"], "hook": "Prix bas", "summary": "Promo", "product_category": "Épicerie", "product_subcategory": "", "ad_objective": "conversion", "promo_type": "prix-barré", "creative_format": "texte", "seasonal_event": "soldes", "layout": "texte-dominant", "cta_style": "texte"}
        m = {"concept": "promo", "tone": "urgence", "score": 82, "tags": ["prix"], "hook": "Prix bas", "summary": "Promo simple", "product_category": "Épicerie", "product_subcategory": "", "ad_objective": "conversion", "promo_type": "prix-barré", "creative_format": "texte", "seasonal_event": "soldes", "layout": "texte-dominant", "cta_style": "texte"}
        fused = self.analyzer._fuse_text_results(g, m, "test-001")
        assert fused["concept"] == "promo"
        assert fused["score"] == 81  # average
        assert "soldes" in fused["tags"]
        assert "prix" in fused["tags"]

    def test_fuse_disagreement_gemini_wins(self):
        """On categorical disagreement, Gemini (first arg) wins."""
        g = {"concept": "promo", "tone": "urgence", "score": 75, "tags": [], "hook": "", "summary": "", "product_category": "Épicerie", "product_subcategory": "", "ad_objective": "conversion", "promo_type": "prix-barré", "creative_format": "texte", "seasonal_event": "soldes", "layout": "texte-dominant", "cta_style": "texte"}
        m = {"concept": "branding", "tone": "aspiration", "score": 70, "tags": [], "hook": "", "summary": "", "product_category": "Boissons", "product_subcategory": "", "ad_objective": "notoriété", "promo_type": "aucune", "creative_format": "texte", "seasonal_event": "aucun", "layout": "texte-dominant", "cta_style": "aucun"}
        fused = self.analyzer._fuse_text_results(g, m, "test-002")
        assert fused["concept"] == "promo"  # Gemini wins
        assert fused["tone"] == "urgence"  # Gemini wins
        assert fused["score"] == 72  # round((75+70)/2)

    def test_fuse_gemini_only(self):
        """When Mistral fails, Gemini result is returned."""
        g = {"concept": "promo", "score": 80, "tags": []}
        fused = self.analyzer._fuse_text_results(g, None, "test-003")
        assert fused["concept"] == "promo"

    def test_fuse_mistral_only(self):
        """When Gemini fails, Mistral result is returned."""
        m = {"concept": "branding", "score": 70, "tags": []}
        fused = self.analyzer._fuse_text_results(None, m, "test-004")
        assert fused["concept"] == "branding"

    def test_fuse_both_fail(self):
        """When both fail, returns None."""
        assert self.analyzer._fuse_text_results(None, None, "test-005") is None

    def test_fuse_longer_summary_wins(self):
        """Longer summary is preferred regardless of source."""
        g = {"concept": "promo", "tone": "urgence", "score": 80, "tags": [], "hook": "Court", "summary": "Court", "product_category": "", "product_subcategory": "", "ad_objective": "", "promo_type": "", "creative_format": "", "seasonal_event": "", "layout": "", "cta_style": ""}
        m = {"concept": "promo", "tone": "urgence", "score": 80, "tags": [], "hook": "Un hook beaucoup plus long et détaillé", "summary": "Un résumé beaucoup plus long et détaillé avec des insights", "product_category": "", "product_subcategory": "", "ad_objective": "", "promo_type": "", "creative_format": "", "seasonal_event": "", "layout": "", "cta_style": ""}
        fused = self.analyzer._fuse_text_results(g, m, "test-006")
        assert "détaillé" in fused["summary"]
        assert "détaillé" in fused["hook"]


# ── Video + text-only analysis tests ─────────────────────────

def test_analyze_all_includes_video_with_text(client, db, test_competitor, adv_headers):
    """Video ads with text should NOT be skipped."""
    ad = Ad(
        competitor_id=test_competitor.id,
        ad_id="google-video-001",
        platform="google",
        display_format="VIDEO",
        ad_text="Profitez de -50% sur tout le rayon bricolage chez Leroy Merlin",
        is_active=True,
    )
    db.add(ad)
    db.commit()

    # The ad should be included in candidates (not skipped)
    unanalyzed = db.query(Ad).filter(
        Ad.creative_analyzed_at.is_(None),
        Ad.ad_text.isnot(None),
    ).all()
    assert any(a.ad_id == "google-video-001" for a in unanalyzed)


def test_analyze_all_skips_video_without_text(client, db, test_competitor, adv_headers):
    """Video ads without text should be skipped."""
    ad = Ad(
        competitor_id=test_competitor.id,
        ad_id="meta-video-001",
        platform="facebook",
        display_format="VIDEO",
        ad_text="",
        creative_url="https://video.fbcdn.net/v/something",
        is_active=True,
    )
    db.add(ad)
    db.commit()
    # This ad has no text and is VIDEO — should be skippable


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

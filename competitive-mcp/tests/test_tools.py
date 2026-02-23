"""Tests unitaires pour les tools MCP de veille concurrentielle."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# ── Fixtures ──────────────────────────────────────────────────────


class FakeCompetitor:
    def __init__(self, id=1, name="Carrefour", is_brand=False, website="https://carrefour.fr"):
        self.id = id
        self.name = name
        self.is_brand = is_brand
        self.website = website
        self.is_active = True


class FakeInstagram:
    def __init__(self, competitor_id=1, followers=500000, engagement_rate=2.5, posts_count=1200, avg_likes=5000.0, recorded_at=None):
        self.competitor_id = competitor_id
        self.followers = followers
        self.engagement_rate = engagement_rate
        self.posts_count = posts_count
        self.avg_likes = avg_likes
        self.recorded_at = recorded_at or datetime.utcnow()


class FakeTikTok:
    def __init__(self, competitor_id=1, followers=300000, likes=5000000, videos_count=200, recorded_at=None):
        self.competitor_id = competitor_id
        self.followers = followers
        self.likes = likes
        self.videos_count = videos_count
        self.recorded_at = recorded_at or datetime.utcnow()


class FakeYouTube:
    def __init__(self, competitor_id=1, subscribers=100000, total_views=10000000, videos_count=50, engagement_rate=1.5, recorded_at=None):
        self.competitor_id = competitor_id
        self.subscribers = subscribers
        self.total_views = total_views
        self.videos_count = videos_count
        self.engagement_rate = engagement_rate
        self.recorded_at = recorded_at or datetime.utcnow()


class FakeAppData:
    def __init__(self, competitor_id=1, store="playstore", rating=4.2, reviews_count=50000, downloads="10M+", downloads_numeric=10000000, app_name="Carrefour", version="5.0", recorded_at=None):
        self.competitor_id = competitor_id
        self.store = store
        self.rating = rating
        self.reviews_count = reviews_count
        self.downloads = downloads
        self.downloads_numeric = downloads_numeric
        self.app_name = app_name
        self.version = version
        self.recorded_at = recorded_at or datetime.utcnow()


class FakeAd:
    def __init__(self, **kwargs):
        defaults = {
            "id": 1, "competitor_id": 1, "ad_id": "ad_001", "platform": "facebook",
            "display_format": "IMAGE", "is_active": True, "ad_text": "Promo exceptionnelle",
            "creative_url": "https://example.com/img.jpg", "start_date": datetime.utcnow(),
            "end_date": None, "estimated_spend_min": 100.0, "estimated_spend_max": 500.0,
            "impressions_min": 10000, "impressions_max": 50000, "eu_total_reach": 25000,
            "publisher_platforms": '["FACEBOOK","INSTAGRAM"]', "product_category": "Épicerie",
            "creative_score": 75, "creative_concept": "promo", "creative_tone": "urgence",
            "creative_hook": "Offre limitée !", "creative_summary": "Pub promo épicerie",
            "creative_analyzed_at": datetime.utcnow(), "product_subcategory": "Boissons",
            "ad_objective": "conversion", "location_audience": None, "page_name": "Carrefour",
            "creative_dominant_colors": '["#FF0000"]', "creative_has_product": True,
            "creative_has_face": False, "creative_has_logo": True, "creative_layout": "single-image",
            "creative_cta_style": "button", "creative_text_overlay": "Promo", "creative_tags": '["promo"]',
            "creative_analysis": '{}', "promo_type": "prix-barré", "creative_format": "produit-unique",
            "price_visible": True, "price_value": "2.99€", "seasonal_event": "aucun",
            "link_url": None, "cta": None, "title": None, "link_description": None,
            "byline": None, "disclaimer_label": None, "payer": None, "beneficiary": None,
            "page_id": None, "page_categories": None, "page_like_count": None,
            "page_profile_uri": None, "page_profile_picture_url": None, "ad_library_url": None,
            "targeted_countries": None, "ad_categories": None, "contains_ai_content": None,
            "ad_type": None, "age_min": None, "age_max": None, "gender_audience": None,
            "age_country_gender_reach": None,
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


class FakeSignal:
    def __init__(self, **kwargs):
        defaults = {
            "id": 1, "competitor_id": 1, "signal_type": "follower_spike",
            "severity": "warning", "platform": "instagram",
            "title": "Pic de followers Carrefour", "description": "+15% en 24h",
            "metric_name": "followers", "previous_value": 450000, "current_value": 520000,
            "change_percent": 15.6, "is_brand": False, "is_read": False,
            "detected_at": datetime.utcnow(),
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


class FakeStoreLocation:
    def __init__(self, **kwargs):
        defaults = {
            "id": 1, "competitor_id": 1, "name": "Carrefour Lille",
            "brand_name": "Carrefour", "city": "Lille", "department": "59",
            "google_rating": 4.1, "google_reviews_count": 250,
            "latitude": 50.63, "longitude": 3.06,
            "category": None, "category_code": None, "address": None,
            "postal_code": None, "siret": None, "source": None,
            "google_place_id": None, "rating_fetched_at": None,
            "recorded_at": datetime.utcnow(),
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


class FakeSocialPost:
    def __init__(self, **kwargs):
        defaults = {
            "id": 1, "competitor_id": 1, "platform": "tiktok",
            "post_id": "tt_001", "title": "Recette rapide",
            "views": 500000, "likes": 25000, "comments": 300, "shares": 1200,
            "url": "https://tiktok.com/@carrefour/video/001",
            "content_theme": "recette", "content_tone": "fun",
            "content_summary": "Recette rapide avec produits Carrefour",
            "content_engagement_score": 85, "published_at": datetime.utcnow(),
            "description": None, "thumbnail_url": None, "duration": None,
            "collected_at": datetime.utcnow(), "content_analysis": None,
            "content_hook": None, "content_format": None, "content_cta": None,
            "content_hashtags": None, "content_mentions": None,
            "content_virality_factors": None, "content_analyzed_at": None,
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


class FakeSerpResult:
    def __init__(self, **kwargs):
        defaults = {
            "id": 1, "competitor_id": 1, "keyword": "supermarché en ligne",
            "position": 1, "title": "Carrefour - Courses en ligne",
            "url": "https://carrefour.fr", "domain": "carrefour.fr",
            "snippet": "Faites vos courses en ligne", "recorded_at": datetime.utcnow(),
            "user_id": None, "advertiser_id": None,
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


class FakeGeoResult:
    def __init__(self, **kwargs):
        defaults = {
            "id": 1, "competitor_id": 1, "keyword": "meilleur supermarché",
            "platform": "claude", "mentioned": True, "recommended": True,
            "sentiment": "positif", "context_snippet": "Carrefour est recommandé pour...",
            "recorded_at": datetime.utcnow(), "query": None, "raw_answer": None,
            "analysis": None, "position_in_answer": 1, "primary_recommendation": None,
            "user_id": None, "advertiser_id": None,
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


class FakeSnapchatData:
    def __init__(self, **kwargs):
        defaults = {
            "id": 1, "competitor_id": 1, "subscribers": 50000,
            "engagement_rate": 1.2, "spotlight_count": 15,
            "recorded_at": datetime.utcnow(), "title": None,
            "story_count": None, "total_views": None,
            "total_shares": None, "total_comments": None,
            "profile_picture_url": None,
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


# ── Formatting Tests ──────────────────────────────────────────────

class TestFormatting:
    def test_format_number_millions(self):
        from competitive_mcp.formatting import format_number
        assert format_number(1_500_000) == "1.5M"

    def test_format_number_thousands(self):
        from competitive_mcp.formatting import format_number
        assert format_number(45_000) == "45K"

    def test_format_number_small(self):
        from competitive_mcp.formatting import format_number
        assert format_number(500) == "500"

    def test_format_number_none(self):
        from competitive_mcp.formatting import format_number
        assert format_number(None) == "N/A"

    def test_format_number_suffix(self):
        from competitive_mcp.formatting import format_number
        assert format_number(2_000_000, " abonnés") == "2.0M abonnés"

    def test_format_euros(self):
        from competitive_mcp.formatting import format_euros
        assert format_euros(2500) == "2.5K EUR"
        assert format_euros(1_200_000) == "1.2M EUR"
        assert format_euros(None) == "N/A"
        assert format_euros(0) == "N/A"
        assert format_euros(50) == "50 EUR"

    def test_truncate(self):
        from competitive_mcp.formatting import truncate
        assert truncate("Hello world", 20) == "Hello world"
        assert truncate("A" * 200, 10) == "A" * 9 + "…"
        assert truncate(None) == ""
        assert truncate("") == ""

    def test_format_date(self):
        from competitive_mcp.formatting import format_date
        dt = datetime(2026, 2, 15)
        assert format_date(dt) == "15/02/2026"
        assert format_date(None) == "N/A"

    def test_format_percent(self):
        from competitive_mcp.formatting import format_percent
        assert format_percent(2.567) == "2.6%"
        assert format_percent(None) == "N/A"

    def test_format_rating(self):
        from competitive_mcp.formatting import format_rating
        assert format_rating(4.2) == "4.2/5"
        assert format_rating(None) == "N/A"


# ── DB Helper Tests ───────────────────────────────────────────────

class TestDBHelpers:
    def test_find_competitor_exact(self):
        from competitive_mcp.db import find_competitor
        mock_db = MagicMock()
        fake_comp = FakeCompetitor()
        mock_db.query.return_value.filter.return_value.first.return_value = fake_comp
        result = find_competitor(mock_db, "Carrefour")
        assert result == fake_comp

    def test_find_competitor_not_found(self):
        from competitive_mcp.db import find_competitor
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = find_competitor(mock_db, "InexistantMagasin")
        assert result is None

    def test_get_all_competitors(self):
        from competitive_mcp.db import get_all_competitors
        mock_db = MagicMock()
        comps = [FakeCompetitor(id=1, name="Carrefour"), FakeCompetitor(id=2, name="Lidl")]
        mock_db.query.return_value.filter.return_value.all.return_value = comps
        result = get_all_competitors(mock_db, include_brand=True)
        assert len(result) == 2


# ── Tool Output Tests ─────────────────────────────────────────────

class TestDashboardTool:
    @patch("competitive_mcp.tools.dashboard.get_session")
    @patch("competitive_mcp.tools.dashboard.get_all_competitors")
    @patch("competitive_mcp.tools.dashboard._batch_latest")
    def test_dashboard_overview_no_competitors(self, mock_batch, mock_comps, mock_session):
        from competitive_mcp.tools.dashboard import get_dashboard_overview
        mock_session.return_value = MagicMock()
        mock_comps.return_value = []
        result = get_dashboard_overview()
        assert "Aucun concurrent" in result

    @patch("competitive_mcp.tools.dashboard.get_session")
    @patch("competitive_mcp.tools.dashboard.get_all_competitors")
    @patch("competitive_mcp.tools.dashboard._batch_latest")
    def test_dashboard_overview_with_data(self, mock_batch, mock_comps, mock_session):
        from competitive_mcp.tools.dashboard import get_dashboard_overview
        db = MagicMock()
        mock_session.return_value = db

        comps = [
            FakeCompetitor(id=1, name="Carrefour"),
            FakeCompetitor(id=5, name="Auchan", is_brand=True),
        ]
        mock_comps.return_value = comps

        mock_batch.return_value = {}
        db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []

        result = get_dashboard_overview()
        assert "Dashboard" in result
        assert "Carrefour" in result


class TestCompetitorTools:
    @patch("competitive_mcp.tools.competitors.get_session")
    @patch("competitive_mcp.tools.competitors.get_all_competitors")
    @patch("competitive_mcp.tools.competitors._batch_latest")
    def test_list_competitors(self, mock_batch, mock_comps, mock_session):
        from competitive_mcp.tools.competitors import list_competitors
        db = MagicMock()
        mock_session.return_value = db
        mock_comps.return_value = [FakeCompetitor(id=1, name="Carrefour")]
        mock_batch.return_value = {}
        db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []

        result = list_competitors()
        assert "Carrefour" in result
        assert "1 Concurrents" in result

    @patch("competitive_mcp.tools.competitors.get_session")
    @patch("competitive_mcp.tools.competitors.find_competitor")
    def test_get_competitor_detail_not_found(self, mock_find, mock_session):
        from competitive_mcp.tools.competitors import get_competitor_detail
        mock_session.return_value = MagicMock()
        mock_find.return_value = None
        result = get_competitor_detail("Inexistant")
        assert "non trouvé" in result

    @patch("competitive_mcp.tools.competitors.get_session")
    @patch("competitive_mcp.tools.competitors.find_competitor")
    def test_get_competitor_detail_found(self, mock_find, mock_session):
        from competitive_mcp.tools.competitors import get_competitor_detail
        db = MagicMock()
        mock_session.return_value = db
        mock_find.return_value = FakeCompetitor(id=1, name="Carrefour", website="https://carrefour.fr")

        # Mock DB queries for each data type
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        db.query.return_value.filter.return_value.scalar.return_value = 0

        result = get_competitor_detail("Carrefour")
        assert "Carrefour" in result

    @patch("competitive_mcp.tools.competitors.get_session")
    @patch("competitive_mcp.tools.competitors.find_competitor")
    @patch("competitive_mcp.tools.competitors._batch_latest")
    def test_compare_competitors_insufficient(self, mock_batch, mock_find, mock_session):
        from competitive_mcp.tools.competitors import compare_competitors
        mock_session.return_value = MagicMock()
        mock_find.return_value = None
        result = compare_competitors(["Carrefour", "Lidl"])
        assert "au moins 2" in result


class TestAdTools:
    @patch("competitive_mcp.tools.ads.get_session")
    def test_search_ads_no_results(self, mock_session):
        from competitive_mcp.tools.ads import search_ads
        db = MagicMock()
        mock_session.return_value = db
        db.query.return_value.join.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        result = search_ads()
        assert "Aucune publicité" in result

    @patch("competitive_mcp.tools.ads.get_session")
    @patch("competitive_mcp.tools.ads.get_all_competitors")
    def test_ad_intelligence_no_competitors(self, mock_comps, mock_session):
        from competitive_mcp.tools.ads import get_ad_intelligence
        mock_session.return_value = MagicMock()
        mock_comps.return_value = []
        result = get_ad_intelligence()
        assert "Aucun concurrent" in result


class TestCreativeTools:
    @patch("competitive_mcp.tools.creative.get_session")
    def test_creative_insights_no_data(self, mock_session):
        from competitive_mcp.tools.creative import get_creative_insights
        db = MagicMock()
        mock_session.return_value = db
        db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = get_creative_insights()
        assert "Aucune publicité analysée" in result


class TestSocialTools:
    @patch("competitive_mcp.tools.social.get_session")
    @patch("competitive_mcp.tools.social.get_all_competitors")
    def test_social_metrics_no_data(self, mock_comps, mock_session):
        from competitive_mcp.tools.social import get_social_metrics
        db = MagicMock()
        mock_session.return_value = db
        mock_comps.return_value = []
        result = get_social_metrics()
        assert "Aucun concurrent" in result

    @patch("competitive_mcp.tools.social.get_session")
    def test_top_posts_no_data(self, mock_session):
        from competitive_mcp.tools.social import get_top_social_posts
        db = MagicMock()
        mock_session.return_value = db
        db.query.return_value.join.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        result = get_top_social_posts()
        assert "Aucun post" in result


class TestSignalTools:
    @patch("competitive_mcp.tools.signals.get_session")
    @patch("competitive_mcp.tools.signals.get_all_competitors")
    def test_signals_no_competitors(self, mock_comps, mock_session):
        from competitive_mcp.tools.signals import get_signals
        mock_session.return_value = MagicMock()
        mock_comps.return_value = []
        result = get_signals()
        assert "Aucun concurrent" in result


class TestStoreTools:
    @patch("competitive_mcp.tools.stores.get_session")
    def test_store_locations_no_data(self, mock_session):
        from competitive_mcp.tools.stores import get_store_locations
        db = MagicMock()
        mock_session.return_value = db
        db.query.return_value.count.return_value = 0
        result = get_store_locations()
        assert "Aucun magasin" in result


class TestSeoGeoTools:
    @patch("competitive_mcp.tools.seo_geo.get_session")
    @patch("competitive_mcp.tools.seo_geo.get_all_competitors")
    def test_seo_no_competitors(self, mock_comps, mock_session):
        from competitive_mcp.tools.seo_geo import get_seo_rankings
        mock_session.return_value = MagicMock()
        mock_comps.return_value = []
        result = get_seo_rankings()
        assert "Aucun concurrent" in result


# ── Score Calculation Tests ───────────────────────────────────────

class TestScoreCalculation:
    def test_calc_score_full(self):
        from competitive_mcp.tools.dashboard import _calc_score
        score = _calc_score(4.5, 5_000_000, 800_000)
        assert 0 <= score <= 100
        assert score > 50

    def test_calc_score_no_data(self):
        from competitive_mcp.tools.dashboard import _calc_score
        assert _calc_score(None, None, None) == 0

    def test_calc_score_partial(self):
        from competitive_mcp.tools.dashboard import _calc_score
        score = _calc_score(4.0, None, None)
        assert score == round((4.0 / 5.0) * 40, 1)


# ── Spend Estimation Tests ───────────────────────────────────────

class TestSpendEstimation:
    def test_estimate_spend_declared(self):
        from competitive_mcp.tools.ads import _estimate_spend
        ad = FakeAd(estimated_spend_min=100, estimated_spend_max=500)
        assert _estimate_spend(ad) == (100, 500)

    def test_estimate_spend_impressions(self):
        from competitive_mcp.tools.ads import _estimate_spend
        ad = FakeAd(estimated_spend_min=None, estimated_spend_max=None, impressions_min=10000, impressions_max=50000)
        result = _estimate_spend(ad)
        assert result[0] > 0
        assert result[1] >= result[0]

    def test_estimate_spend_reach(self):
        from competitive_mcp.tools.ads import _estimate_spend
        ad = FakeAd(estimated_spend_min=None, estimated_spend_max=None, impressions_min=None, impressions_max=None, eu_total_reach=50000)
        result = _estimate_spend(ad)
        assert result[0] > 0

    def test_estimate_spend_nothing(self):
        from competitive_mcp.tools.ads import _estimate_spend
        ad = FakeAd(estimated_spend_min=None, estimated_spend_max=None, impressions_min=None, impressions_max=None, eu_total_reach=None)
        assert _estimate_spend(ad) == (0, 0)

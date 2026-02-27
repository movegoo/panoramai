"""Tests for Meta Ad Library API migration (ScrapeCreators → Meta API primary)."""
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from database import Ad, Competitor
from services.scheduler import DataCollectionScheduler


# ── Sample Meta API responses ──────────────────────────────────────────

SAMPLE_META_AD = {
    "id": "123456789",
    "ad_creation_time": "2025-01-15T10:00:00+0000",
    "ad_delivery_start_time": "2025-01-16T00:00:00+0000",
    "ad_delivery_stop_time": None,
    "page_id": "999888777",
    "page_name": "Carrefour France",
    "bylines": "Paid for by Carrefour",
    "publisher_platforms": ["facebook", "instagram"],
    "ad_snapshot_url": "https://www.facebook.com/ads/archive/render_ad/?id=123456789",
    "eu_total_reach": 150000,
    "ad_creative_bodies": ["Découvrez nos offres de la semaine !"],
    "ad_creative_link_titles": ["Offres Carrefour"],
    "ad_creative_link_captions": ["carrefour.fr"],
    "ad_creative_link_descriptions": ["Les meilleures promos près de chez vous"],
    "beneficiary_payers": [{"payer": "Carrefour SA", "beneficiary": "Carrefour France"}],
    "impressions": {"lower_bound": "10000", "upper_bound": "50000"},
    "spend": {"lower_bound": "500", "upper_bound": "1500"},
    "target_ages": "18-65+",
    "target_gender": "All",
    "target_locations": [{"name": "France"}],
    "languages": ["fr"],
    "estimated_audience_size": {"lower_bound": "1000000", "upper_bound": "5000000"},
    "currency": "EUR",
}

SAMPLE_META_AD_NO_CREATIVE = {
    "id": "987654321",
    "ad_delivery_start_time": "2025-02-01T00:00:00+0000",
    "ad_delivery_stop_time": "2025-02-15T00:00:00+0000",
    "page_id": "999888777",
    "page_name": "Carrefour France",
    "publisher_platforms": ["facebook"],
    "ad_snapshot_url": "https://www.facebook.com/ads/archive/render_ad/?id=987654321",
    "eu_total_reach": 5000,
    "ad_creative_bodies": [],
    "ad_creative_link_titles": [],
    "beneficiary_payers": [],
    "impressions": {},
    "spend": {},
}

SAMPLE_SEARCHAPI_DETAIL = {
    "aaa_info": {
        "eu_total_reach": 250000,
        "payer_beneficiary_data": [
            {"payer": "Carrefour SA", "beneficiary": "Carrefour France"}
        ],
        "age_country_gender_reach_breakdown": [
            {"country": "FR", "age_range": "25-34", "male": 30000, "female": 40000}
        ],
        "location_audience": [{"name": "France", "type": "country"}],
    }
}


# ── Test _store_meta_api_ads mapping ───────────────────────────────────

class TestStoreMetaApiAds:
    """Test the Meta API response → Ad model mapping."""

    def _parse_date(self, date_str):
        """Simple date parser for tests."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("+0000", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def test_maps_full_ad_correctly(self, db):
        """Meta API ad with all fields maps correctly to Ad model."""
        comp = Competitor(name="Carrefour", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)

        scheduler = DataCollectionScheduler()
        count = scheduler._store_meta_api_ads(db, comp, [SAMPLE_META_AD], self._parse_date)

        assert count == 1
        ad = db.query(Ad).filter(Ad.ad_id == "123456789").first()
        assert ad is not None
        assert ad.competitor_id == comp.id
        assert ad.platform == "instagram"  # instagram in publisher_platforms
        assert ad.ad_text == "Découvrez nos offres de la semaine !"
        assert ad.title == "Offres Carrefour"
        assert ad.link_description == "Les meilleures promos près de chez vous"
        assert ad.page_id == "999888777"
        assert ad.page_name == "Carrefour France"
        assert ad.ad_library_url == "https://www.facebook.com/ads/archive/render_ad/?id=123456789"
        assert ad.eu_total_reach == 150000
        assert ad.impressions_min == 10000
        assert ad.impressions_max == 50000
        assert ad.estimated_spend_min == 500.0
        assert ad.estimated_spend_max == 1500.0
        assert ad.payer == "Carrefour SA"
        assert ad.beneficiary == "Carrefour France"
        assert ad.is_active is True
        assert ad.creative_url == ""  # Not available via Meta API
        assert ad.cta == ""  # Not available via Meta API

    def test_maps_ad_with_empty_fields(self, db):
        """Meta API ad with empty creative fields maps gracefully."""
        comp = Competitor(name="Carrefour", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)

        scheduler = DataCollectionScheduler()
        count = scheduler._store_meta_api_ads(db, comp, [SAMPLE_META_AD_NO_CREATIVE], self._parse_date)

        assert count == 1
        ad = db.query(Ad).filter(Ad.ad_id == "987654321").first()
        assert ad is not None
        assert ad.ad_text == ""
        assert ad.title is None
        assert ad.payer is None
        assert ad.beneficiary is None
        assert ad.impressions_min is None
        assert ad.is_active is False  # has end_date

    def test_skips_duplicate_ads(self, db):
        """Already-stored ad_id is skipped."""
        comp = Competitor(name="Carrefour", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)

        # Pre-insert the ad
        existing = Ad(competitor_id=comp.id, ad_id="123456789", platform="facebook")
        db.add(existing)
        db.commit()

        scheduler = DataCollectionScheduler()
        count = scheduler._store_meta_api_ads(db, comp, [SAMPLE_META_AD], self._parse_date)
        assert count == 0

    def test_facebook_only_platform(self, db):
        """Ad with only facebook in publisher_platforms maps to 'facebook'."""
        comp = Competitor(name="Carrefour", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)

        ad_data = {**SAMPLE_META_AD, "id": "111222333", "publisher_platforms": ["facebook"]}
        scheduler = DataCollectionScheduler()
        count = scheduler._store_meta_api_ads(db, comp, [ad_data], self._parse_date)

        assert count == 1
        ad = db.query(Ad).filter(Ad.ad_id == "111222333").first()
        assert ad.platform == "facebook"

    def test_multiple_ads_batch(self, db):
        """Multiple ads are stored correctly in a single batch."""
        comp = Competitor(name="Carrefour", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)

        ads = [
            {**SAMPLE_META_AD, "id": "ad_001"},
            {**SAMPLE_META_AD, "id": "ad_002"},
            {**SAMPLE_META_AD, "id": "ad_003"},
        ]
        scheduler = DataCollectionScheduler()
        count = scheduler._store_meta_api_ads(db, comp, ads, self._parse_date)
        assert count == 3


# ── Test _fetch_ads fallback logic ─────────────────────────────────────

class TestFetchAdsFallback:
    """Test that _fetch_ads uses Meta API primary and falls back to ScrapeCreators."""

    @pytest.mark.asyncio
    async def test_uses_meta_api_when_page_id_exists(self, db):
        """When competitor has facebook_page_id and Meta API works, uses Meta API."""
        comp = Competitor(name="Carrefour", facebook_page_id="999888777", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)

        mock_meta = AsyncMock()
        mock_meta.is_configured = True
        mock_meta.get_active_ads = AsyncMock(return_value=[SAMPLE_META_AD])

        scheduler = DataCollectionScheduler()
        with patch("services.scheduler.DataCollectionScheduler._store_meta_api_ads", return_value=1) as mock_store:
            with patch.dict("sys.modules", {"services.meta_ad_library": MagicMock(meta_ad_library=mock_meta)}):
                await scheduler._fetch_ads(db, comp, "Carrefour")

            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_scrapecreators_on_meta_failure(self, db):
        """When Meta API fails, falls back to ScrapeCreators."""
        comp = Competitor(name="Carrefour", facebook_page_id="999888777", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)

        mock_meta = AsyncMock()
        mock_meta.is_configured = True
        mock_meta.get_active_ads = AsyncMock(side_effect=Exception("Meta API down"))

        mock_sc = AsyncMock()
        mock_sc.fetch_facebook_company_ads = AsyncMock(return_value={"success": True, "ads": [], "cursor": None})

        scheduler = DataCollectionScheduler()
        with patch.dict("sys.modules", {
            "services.meta_ad_library": MagicMock(meta_ad_library=mock_meta),
            "services.scrapecreators": MagicMock(scrapecreators=mock_sc),
        }):
            await scheduler._fetch_ads(db, comp, "Carrefour")

        mock_sc.fetch_facebook_company_ads.assert_called()

    @pytest.mark.asyncio
    async def test_uses_scrapecreators_when_no_page_id(self, db):
        """When competitor has no facebook_page_id, uses ScrapeCreators search."""
        comp = Competitor(name="Carrefour", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)

        mock_sc = AsyncMock()
        mock_sc.search_facebook_ads = AsyncMock(return_value={"success": True, "ads": []})

        scheduler = DataCollectionScheduler()
        with patch.dict("sys.modules", {"services.scrapecreators": MagicMock(scrapecreators=mock_sc)}):
            await scheduler._fetch_ads(db, comp, "Carrefour")

        mock_sc.search_facebook_ads.assert_called_once()


# ── Test _enrich_transparency with SearchAPI primary ───────────────────

class TestEnrichTransparency:
    """Test enrichment uses SearchAPI primary, ScrapeCreators fallback."""

    @pytest.mark.asyncio
    async def test_uses_searchapi_when_configured(self, db):
        """When SearchAPI key is configured, uses meta_ad_library.enrich_ad_details."""
        comp = Competitor(name="Carrefour", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)

        ad = Ad(competitor_id=comp.id, ad_id="test_ad_001", platform="facebook")
        db.add(ad)
        db.commit()

        mock_meta = MagicMock()
        mock_meta.searchapi_key = "test-key"
        mock_meta.enrich_ad_details = AsyncMock(return_value={
            "eu_total_reach": 250000,
            "payer": "Carrefour SA",
            "beneficiary": "Carrefour France",
            "age_gender_data": [{"country": "FR"}],
            "location_data": [{"name": "France"}],
        })

        scheduler = DataCollectionScheduler()
        with patch.dict("sys.modules", {"services.meta_ad_library": MagicMock(meta_ad_library=mock_meta)}):
            await scheduler._enrich_transparency(db)

        db.refresh(ad)
        assert ad.eu_total_reach == 250000
        assert ad.payer == "Carrefour SA"
        assert ad.beneficiary == "Carrefour France"

    @pytest.mark.asyncio
    async def test_falls_back_to_scrapecreators_when_no_searchapi(self, db):
        """When SearchAPI is not configured, falls back to ScrapeCreators."""
        comp = Competitor(name="Carrefour", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)

        ad = Ad(competitor_id=comp.id, ad_id="test_ad_002", platform="facebook")
        db.add(ad)
        db.commit()

        mock_meta = MagicMock()
        mock_meta.searchapi_key = ""  # Not configured

        mock_sc = AsyncMock()
        mock_sc.get_facebook_ad_detail = AsyncMock(return_value={
            "success": True,
            "eu_total_reach": 100000,
            "age_min": 18,
            "age_max": 65,
            "gender_audience": "All",
            "payer": "Carrefour",
            "beneficiary": "Carrefour France",
        })

        scheduler = DataCollectionScheduler()
        with patch.dict("sys.modules", {
            "services.meta_ad_library": MagicMock(meta_ad_library=mock_meta),
            "services.scrapecreators": MagicMock(scrapecreators=mock_sc),
        }):
            await scheduler._enrich_transparency(db)

        db.refresh(ad)
        assert ad.eu_total_reach == 100000
        mock_sc.get_facebook_ad_detail.assert_called_once_with("test_ad_002")


# ── Test enrich_ad_details in MetaAdLibraryService ─────────────────────

class TestEnrichAdDetails:
    """Test the new enrich_ad_details method in MetaAdLibraryService."""

    @pytest.mark.asyncio
    async def test_returns_enrichment_data(self):
        """Returns payer, beneficiary, eu_total_reach from SearchAPI response."""
        from services.meta_ad_library import MetaAdLibraryService

        service = MetaAdLibraryService()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_SEARCHAPI_DETAIL
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.dict(os.environ, {"SEARCHAPI_KEY": "test-key"}):
            with patch("services.meta_ad_library.httpx.AsyncClient", return_value=mock_client):
                result = await service.enrich_ad_details("123456789")

        assert result is not None
        assert result["eu_total_reach"] == 250000
        assert result["payer"] == "Carrefour SA"
        assert result["beneficiary"] == "Carrefour France"
        assert len(result["age_gender_data"]) == 1

    @pytest.mark.asyncio
    async def test_returns_none_without_searchapi_key(self):
        """Returns None when SearchAPI key is not configured."""
        from services.meta_ad_library import MetaAdLibraryService

        service = MetaAdLibraryService()

        with patch.dict(os.environ, {"SEARCHAPI_KEY": ""}, clear=False):
            # Also patch settings to ensure no fallback
            with patch("services.meta_ad_library.settings") as mock_settings:
                mock_settings.SEARCHAPI_KEY = ""
                result = await service.enrich_ad_details("123456789")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self):
        """Returns None on HTTP error (graceful failure)."""
        from services.meta_ad_library import MetaAdLibraryService

        service = MetaAdLibraryService()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(side_effect=Exception("HTTP 500"))

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.dict(os.environ, {"SEARCHAPI_KEY": "test-key"}):
            with patch("services.meta_ad_library.httpx.AsyncClient", return_value=mock_client):
                result = await service.enrich_ad_details("123456789")

        assert result is None

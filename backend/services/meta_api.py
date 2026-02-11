"""
Service Meta Marketing API.
Intégration complète : Ads Library + Marketing API + Instagram Graph API.
"""
import httpx
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class MetaAdStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"


class MetaPlatform(str, Enum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    MESSENGER = "messenger"
    AUDIENCE_NETWORK = "audience_network"


# =============================================================================
# Configuration
# =============================================================================

GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
ADS_LIBRARY_API = f"{GRAPH_API_BASE}/ads_archive"


class MetaAPIService:
    """Service unifié pour les APIs Meta."""

    def __init__(self):
        self.access_token = os.getenv("META_ACCESS_TOKEN")
        self.app_id = os.getenv("META_APP_ID")
        self.app_secret = os.getenv("META_APP_SECRET")
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token)

    async def _get_client(self) -> httpx.AsyncClient:
        if not self._client:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # Ads Library API (Public - Competitor Research)
    # =========================================================================

    async def search_ads_library(
        self,
        page_id: Optional[str] = None,
        search_terms: Optional[str] = None,
        countries: str = "FR",
        ad_type: str = "ALL",
        limit: int = 100,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Recherche dans la bibliothèque publicitaire Meta.

        Args:
            page_id: ID de la page Facebook (pour rechercher les pubs d'une marque)
            search_terms: Termes de recherche libre
            countries: Pays de diffusion (FR, BE, CH, etc.)
            ad_type: ALL, POLITICAL_AND_ISSUE_ADS, etc.
            limit: Nombre max de résultats
            after: Cursor pour pagination
        """
        if not self.is_configured:
            raise ValueError("META_ACCESS_TOKEN not configured")

        params = {
            "access_token": self.access_token,
            "ad_reached_countries": countries,
            "ad_type": ad_type,
            "fields": ",".join([
                "id",
                "ad_creation_time",
                "ad_creative_bodies",
                "ad_creative_link_captions",
                "ad_creative_link_descriptions",
                "ad_creative_link_titles",
                "ad_delivery_start_time",
                "ad_delivery_stop_time",
                "ad_snapshot_url",
                "bylines",
                "currency",
                "estimated_audience_size",
                "impressions",
                "languages",
                "page_id",
                "page_name",
                "publisher_platforms",
                "spend",
                "target_ages",
                "target_gender",
                "target_locations",
            ]),
            "limit": limit,
        }

        if page_id:
            params["search_page_ids"] = page_id
        if search_terms:
            params["search_terms"] = search_terms
        if after:
            params["after"] = after

        client = await self._get_client()
        response = await client.get(ADS_LIBRARY_API, params=params)

        if response.status_code != 200:
            logger.error(f"Ads Library API error: {response.text}")
            return {"data": [], "error": response.json()}

        return response.json()

    async def get_page_ads(
        self,
        page_id: str,
        active_only: bool = True,
        countries: str = "FR",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Récupère toutes les publicités d'une page."""
        all_ads = []
        after = None

        while True:
            result = await self.search_ads_library(
                page_id=page_id,
                countries=countries,
                limit=limit,
                after=after,
            )

            ads = result.get("data", [])

            if active_only:
                ads = [
                    ad for ad in ads
                    if not ad.get("ad_delivery_stop_time")
                ]

            all_ads.extend(ads)

            # Pagination
            paging = result.get("paging", {})
            after = paging.get("cursors", {}).get("after")

            if not after or len(ads) < limit:
                break

        return all_ads

    # =========================================================================
    # Marketing API (Business Account - Own Ads)
    # =========================================================================

    async def get_my_ad_accounts(self) -> List[Dict[str, Any]]:
        """Récupère tous les comptes publicitaires accessibles."""
        if not self.is_configured:
            raise ValueError("META_ACCESS_TOKEN not configured")

        endpoint = f"{GRAPH_API_BASE}/me/adaccounts"
        params = {
            "access_token": self.access_token,
            "fields": "id,name,account_status,amount_spent,currency,business_name",
            "limit": 100,
        }

        all_accounts = []
        client = await self._get_client()

        while endpoint:
            response = await client.get(endpoint, params=params)
            if response.status_code != 200:
                logger.error(f"Ad Accounts API error: {response.text}")
                break

            data = response.json()
            all_accounts.extend(data.get("data", []))

            # Pagination
            endpoint = data.get("paging", {}).get("next")
            params = {}  # URL already contains params

        return all_accounts

    async def get_ad_account_insights(
        self,
        ad_account_id: str,
        date_preset: str = "last_30d",
        breakdown: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Insights de compte publicitaire (propre compte).

        Args:
            ad_account_id: ID du compte pub (act_XXXXX)
            date_preset: Période (today, yesterday, last_7d, last_30d, etc.)
            breakdown: age, gender, country, region, etc.
        """
        if not self.is_configured:
            raise ValueError("META_ACCESS_TOKEN not configured")

        endpoint = f"{GRAPH_API_BASE}/{ad_account_id}/insights"

        params = {
            "access_token": self.access_token,
            "date_preset": date_preset,
            "fields": ",".join([
                "impressions",
                "reach",
                "clicks",
                "spend",
                "cpc",
                "cpm",
                "ctr",
                "actions",
                "cost_per_action_type",
                "frequency",
            ]),
        }

        if breakdown:
            params["breakdowns"] = breakdown

        client = await self._get_client()
        response = await client.get(endpoint, params=params)

        if response.status_code != 200:
            logger.error(f"Marketing API error: {response.text}")
            return {"error": response.json()}

        return response.json()

    async def get_campaigns(
        self,
        ad_account_id: str,
        status_filter: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Liste les campagnes d'un compte publicitaire."""
        endpoint = f"{GRAPH_API_BASE}/{ad_account_id}/campaigns"

        params = {
            "access_token": self.access_token,
            "fields": ",".join([
                "id",
                "name",
                "status",
                "objective",
                "created_time",
                "start_time",
                "stop_time",
                "daily_budget",
                "lifetime_budget",
                "insights{impressions,reach,clicks,spend,cpc,cpm}",
            ]),
            "limit": 100,
        }

        if status_filter:
            params["filtering"] = f'[{{"field":"status","operator":"IN","value":{status_filter}}}]'

        client = await self._get_client()
        response = await client.get(endpoint, params=params)

        if response.status_code != 200:
            logger.error(f"Campaigns API error: {response.text}")
            return []

        return response.json().get("data", [])

    # =========================================================================
    # Instagram Graph API
    # =========================================================================

    async def get_instagram_business_account(
        self,
        page_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Récupère le compte Instagram Business lié à une page Facebook."""
        endpoint = f"{GRAPH_API_BASE}/{page_id}"

        params = {
            "access_token": self.access_token,
            "fields": "instagram_business_account{id,username,name,biography,followers_count,follows_count,media_count,profile_picture_url}",
        }

        client = await self._get_client()
        response = await client.get(endpoint, params=params)

        if response.status_code != 200:
            return None

        data = response.json()
        return data.get("instagram_business_account")

    async def get_instagram_media_insights(
        self,
        ig_user_id: str,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Récupère les posts Instagram avec leurs insights."""
        endpoint = f"{GRAPH_API_BASE}/{ig_user_id}/media"

        params = {
            "access_token": self.access_token,
            "fields": ",".join([
                "id",
                "caption",
                "media_type",
                "media_url",
                "thumbnail_url",
                "permalink",
                "timestamp",
                "like_count",
                "comments_count",
                "insights.metric(impressions,reach,engagement,saved)",
            ]),
            "limit": limit,
        }

        client = await self._get_client()
        response = await client.get(endpoint, params=params)

        if response.status_code != 200:
            logger.error(f"Instagram Media API error: {response.text}")
            return []

        return response.json().get("data", [])

    async def discover_instagram_business(
        self,
        ig_user_id: str,
        username: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Business Discovery API - Découvre un compte Instagram business.
        Permet d'obtenir des infos publiques sur un concurrent.
        """
        endpoint = f"{GRAPH_API_BASE}/{ig_user_id}"

        params = {
            "access_token": self.access_token,
            "fields": f"business_discovery.username({username}){{id,username,name,biography,followers_count,follows_count,media_count,profile_picture_url,media.limit(12){{id,caption,media_type,like_count,comments_count,timestamp,permalink}}}}",
        }

        client = await self._get_client()
        response = await client.get(endpoint, params=params)

        if response.status_code != 200:
            logger.error(f"Business Discovery error: {response.text}")
            return None

        data = response.json()
        return data.get("business_discovery")

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def parse_ad_spend(self, spend_data: Dict) -> Dict[str, float]:
        """Parse les données de dépenses publicitaires."""
        if not spend_data:
            return {"min": 0, "max": 0}

        return {
            "min": float(spend_data.get("lower_bound", 0)),
            "max": float(spend_data.get("upper_bound", 0)),
        }

    def parse_impressions(self, impressions_data: Dict) -> Dict[str, int]:
        """Parse les données d'impressions."""
        if not impressions_data:
            return {"min": 0, "max": 0}

        return {
            "min": int(impressions_data.get("lower_bound", 0)),
            "max": int(impressions_data.get("upper_bound", 0)),
        }

    def extract_targeting(self, ad_data: Dict) -> Dict[str, Any]:
        """Extrait les informations de ciblage d'une pub."""
        return {
            "ages": ad_data.get("target_ages"),
            "gender": ad_data.get("target_gender"),
            "locations": ad_data.get("target_locations", []),
            "languages": ad_data.get("languages", []),
        }

    def calculate_engagement_score(
        self,
        impressions: int,
        clicks: int,
        spend: float,
    ) -> Dict[str, float]:
        """Calcule les métriques d'engagement."""
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        cpc = (spend / clicks) if clicks > 0 else 0
        cpm = (spend / impressions * 1000) if impressions > 0 else 0

        return {
            "ctr": round(ctr, 2),
            "cpc": round(cpc, 2),
            "cpm": round(cpm, 2),
        }


# Singleton
meta_api = MetaAPIService()

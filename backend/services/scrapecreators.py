"""
ScrapeCreators API service.
Unified social media data extraction via https://api.scrapecreators.com
"""
import logging
import httpx
from typing import Dict, Optional
from core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.scrapecreators.com"


class ScrapeCreatorsAPI:
    """Client for the ScrapeCreators social media scraping API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.SCRAPECREATORS_API_KEY
        if not self.api_key:
            logger.warning("ScrapeCreators API key not configured. Set SCRAPECREATORS_API_KEY in .env")

    @property
    def _headers(self) -> dict:
        return {"x-api-key": self.api_key}

    async def _get(self, path: str, params: dict = None) -> Dict:
        """Make a GET request to the ScrapeCreators API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{BASE_URL}{path}",
                    headers=self._headers,
                    params=params or {},
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()

                if not data.get("success"):
                    return {
                        "success": False,
                        "error": data.get("message", "Unknown API error"),
                        "credits_remaining": data.get("credits_remaining")
                    }

                return data

        except httpx.HTTPStatusError as e:
            logger.error(f"ScrapeCreators HTTP error on {path}: {e.response.status_code}")
            return {"success": False, "error": f"HTTP {e.response.status_code}"}
        except httpx.TimeoutException:
            logger.error(f"ScrapeCreators timeout on {path}")
            return {"success": False, "error": "Request timed out"}
        except Exception as e:
            logger.error(f"ScrapeCreators error on {path}: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Instagram
    # =========================================================================

    async def fetch_instagram_profile(self, handle: str) -> Dict:
        """
        Fetch Instagram profile data.

        Returns: followers, following, posts_count, engagement_rate, bio, etc.
        """
        handle = handle.lstrip("@")
        data = await self._get("/v1/instagram/profile", {"handle": handle})

        if not data.get("success"):
            return data

        try:
            user = data["data"]["user"]
            followers = user.get("edge_followed_by", {}).get("count", 0)
            following = user.get("edge_follow", {}).get("count", 0)

            # Posts count
            posts_count = user.get("edge_owner_to_timeline_media", {}).get("count", 0)

            # Calculate engagement from recent posts
            avg_likes = 0
            avg_comments = 0
            engagement_rate = 0.0

            recent_posts = (user.get("edge_owner_to_timeline_media", {})
                           .get("edges", []))
            if recent_posts and followers > 0:
                likes_list = []
                comments_list = []
                for edge in recent_posts[:12]:
                    node = edge.get("node", {})
                    likes_list.append(node.get("edge_liked_by", {}).get("count", 0))
                    comments_list.append(node.get("edge_media_to_comment", {}).get("count", 0))

                if likes_list:
                    avg_likes = sum(likes_list) / len(likes_list)
                    avg_comments = sum(comments_list) / len(comments_list)
                    engagement_rate = round(
                        ((avg_likes + avg_comments) / followers) * 100, 2
                    )

            return {
                "success": True,
                "followers": followers,
                "following": following,
                "posts_count": posts_count,
                "avg_likes": avg_likes,
                "avg_comments": avg_comments,
                "engagement_rate": engagement_rate,
                "bio": user.get("biography", ""),
                "is_verified": user.get("is_verified", False),
                "is_business": user.get("is_business_account", False),
                "full_name": user.get("full_name", ""),
                "profile_pic": user.get("profile_pic_url_hd", ""),
                "credits_remaining": data.get("credits_remaining"),
            }
        except (KeyError, TypeError) as e:
            logger.error(f"Error parsing Instagram response for {handle}: {e}")
            return {"success": False, "error": f"Parse error: {e}"}

    # =========================================================================
    # TikTok
    # =========================================================================

    async def fetch_tiktok_profile(self, handle: str) -> Dict:
        """
        Fetch TikTok profile data.

        Returns: followers, following, likes, videos_count, bio, verified
        """
        handle = handle.lstrip("@")
        data = await self._get("/v1/tiktok/profile", {"handle": handle})

        if not data.get("success"):
            return data

        try:
            user = data.get("user", {})
            stats = data.get("stats", {})

            return {
                "success": True,
                "username": user.get("uniqueId", handle),
                "nickname": user.get("nickname", ""),
                "followers": stats.get("followerCount", 0),
                "following": stats.get("followingCount", 0),
                "likes": stats.get("heartCount", 0) or stats.get("heart", 0),
                "videos_count": stats.get("videoCount", 0),
                "bio": user.get("signature", ""),
                "verified": user.get("verified", False),
                "avatar_url": user.get("avatarLarger", ""),
                "credits_remaining": data.get("credits_remaining"),
            }
        except (KeyError, TypeError) as e:
            logger.error(f"Error parsing TikTok response for {handle}: {e}")
            return {"success": False, "error": f"Parse error: {e}"}

    async def fetch_tiktok_videos(self, handle: str, limit: int = 10) -> Dict:
        """Fetch recent TikTok videos for a user."""
        handle = handle.lstrip("@")
        data = await self._get("/v1/tiktok/profile/videos", {
            "handle": handle,
            "limit": limit
        })

        if not data.get("success"):
            return data

        try:
            videos = []
            for item in data.get("videos", data.get("items", []))[:limit]:
                videos.append({
                    "id": item.get("id"),
                    "description": item.get("desc", item.get("description", "")),
                    "create_time": item.get("createTime"),
                    "views": item.get("stats", {}).get("playCount",
                             item.get("playCount", 0)),
                    "likes": item.get("stats", {}).get("diggCount",
                             item.get("diggCount", 0)),
                    "comments": item.get("stats", {}).get("commentCount",
                                item.get("commentCount", 0)),
                    "shares": item.get("stats", {}).get("shareCount",
                              item.get("shareCount", 0)),
                })

            return {
                "success": True,
                "username": handle,
                "videos": videos,
                "count": len(videos),
            }
        except Exception as e:
            logger.error(f"Error parsing TikTok videos for {handle}: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # YouTube
    # =========================================================================

    async def fetch_youtube_channel(self, handle: str = None, channel_id: str = None) -> Dict:
        """
        Fetch YouTube channel data.

        Pass either handle (e.g. "CarrefourFrance") or channel_id.
        Returns: subscribers, total_views, videos_count, description, etc.
        """
        params = {}
        if handle:
            params["handle"] = handle.lstrip("@")
        elif channel_id:
            params["channelId"] = channel_id
        else:
            return {"success": False, "error": "Provide handle or channel_id"}

        data = await self._get("/v1/youtube/channel", params)

        if not data.get("success"):
            return data

        try:
            return {
                "success": True,
                "channel_id": data.get("channelId", ""),
                "channel_name": data.get("name", ""),
                "description": data.get("description", ""),
                "handle": data.get("handle", ""),
                "subscribers": data.get("subscriberCount", 0),
                "total_views": data.get("viewCount", 0),
                "videos_count": data.get("videoCount", 0),
                "joined_date": data.get("joinedDateText", ""),
                "tags": data.get("tags", ""),
                "credits_remaining": data.get("credits_remaining"),
            }
        except (KeyError, TypeError) as e:
            logger.error(f"Error parsing YouTube response: {e}")
            return {"success": False, "error": f"Parse error: {e}"}

    async def fetch_youtube_videos(self, handle: str = None, channel_id: str = None, limit: int = 10) -> Dict:
        """Fetch recent YouTube videos for a channel."""
        params = {}
        if handle:
            params["handle"] = handle.lstrip("@")
        elif channel_id:
            params["channelId"] = channel_id
        else:
            return {"success": False, "error": "Provide handle or channel_id"}

        data = await self._get("/v1/youtube/channel-videos", params)

        if not data.get("success"):
            return data

        try:
            videos = []
            for item in data.get("videos", [])[:limit]:
                videos.append({
                    "video_id": item.get("videoId", ""),
                    "title": item.get("title", ""),
                    "description": item.get("description", "")[:500],
                    "published_at": item.get("publishedTimeText", ""),
                    "thumbnail_url": item.get("thumbnail", ""),
                    "views": item.get("viewCount", 0),
                    "likes": item.get("likeCount", 0),
                    "comments": item.get("commentCount", 0),
                    "duration": item.get("lengthText", ""),
                })

            return {
                "success": True,
                "videos": videos,
                "count": len(videos),
            }
        except Exception as e:
            logger.error(f"Error parsing YouTube videos: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Facebook
    # =========================================================================

    async def fetch_facebook_profile(self, page_url: str) -> Dict:
        """Fetch Facebook page profile data."""
        data = await self._get("/v1/facebook/profile", {"url": page_url})

        if not data.get("success"):
            return data

        try:
            return {
                "success": True,
                "name": data.get("name", ""),
                "follower_count": data.get("followerCount"),
                "like_count": data.get("likeCount"),
                "rating_count": data.get("ratingCount"),
                "website": data.get("website"),
                "account_status": data.get("account_status"),
                "credits_remaining": data.get("credits_remaining"),
            }
        except Exception as e:
            logger.error(f"Error parsing Facebook response: {e}")
            return {"success": False, "error": str(e)}

    async def get_facebook_ad_detail(self, ad_archive_id: str) -> Dict:
        """
        Fetch detailed ad data including EU transparency (age, gender, location, reach).
        Uses /v1/facebook/adLibrary/ad?id=<adArchiveId>
        """
        data = await self._get("/v1/facebook/adLibrary/ad", {"id": ad_archive_id})

        if not data.get("success"):
            return data

        # Extract EU transparency data from aaa_info or eu_transparency
        eu = data.get("eu_transparency") or data.get("aaa_info") or {}

        return {
            "success": True,
            "ad_archive_id": str(data.get("adArchiveID", ad_archive_id)),
            "age_min": eu.get("age_audience", {}).get("min") if isinstance(eu.get("age_audience"), dict) else None,
            "age_max": eu.get("age_audience", {}).get("max") if isinstance(eu.get("age_audience"), dict) else None,
            "gender_audience": eu.get("gender_audience"),
            "location_audience": eu.get("location_audience", []),
            "eu_total_reach": eu.get("eu_total_reach"),
            "age_country_gender_reach_breakdown": eu.get("age_country_gender_reach_breakdown", []),
            "targets_eu": eu.get("targets_eu", False),
            "credits_remaining": data.get("credits_remaining"),
        }

    async def search_facebook_ads(self, company_name: str, country: str = "FR", limit: int = 30) -> Dict:
        """Search Facebook Ad Library for a company's ads via ScrapeCreators."""
        data = await self._get("/v1/facebook/adLibrary/search/ads", {
            "query": company_name,
            "country": country,
            "limit": str(limit),
        })

        if not data.get("success"):
            return data

        ads = data.get("searchResults", [])
        return {
            "success": True,
            "ads": ads,
            "count": len(ads),
            "total_available": data.get("searchResultsCount", 0),
            "cursor": data.get("cursor"),
            "credits_remaining": data.get("credits_remaining"),
        }

    # =========================================================================
    # Google Ads Transparency
    # =========================================================================

    async def search_google_ads(self, domain: str, country: str = "FR", cursor: str = None) -> Dict:
        """
        Search Google Ads Transparency Center for a company's ads.
        Uses /v1/google/company/ads?domain=<domain>
        Returns: advertiser info, ad format, dates, creative URL, transparency link.
        """
        params = {"domain": domain}
        if country:
            params["country"] = country
        if cursor:
            params["cursor"] = cursor

        data = await self._get("/v1/google/company/ads", params)

        if not data.get("success"):
            return data

        ads = data.get("ads", [])
        return {
            "success": True,
            "ads": ads,
            "count": len(ads),
            "cursor": data.get("cursor"),
            "credits_remaining": data.get("credits_remaining"),
        }

    # =========================================================================
    # TikTok Ads (via keyword search with is_ads detection)
    # =========================================================================

    async def search_tiktok_ads(self, query: str, limit: int = 30) -> Dict:
        """
        Search TikTok for ad/sponsored content related to a brand.
        Uses /v1/tiktok/search/keyword and filters by is_ads flag.
        Returns both organic mentions and detected ads.
        """
        data = await self._get("/v1/tiktok/search/keyword", {
            "query": query,
            "limit": str(limit),
        })

        if not data.get("success"):
            return data

        try:
            all_items = data.get("search_item_list", [])
            ads = []
            for item in all_items:
                v = item.get("aweme_info", {})
                commerce = v.get("commerce_info", {})
                is_ad = v.get("is_ads", False) or commerce.get("ad_source", 0) > 0
                branded = commerce.get("branded_content_type", 0) > 0

                if not (is_ad or branded):
                    continue

                author = v.get("author", {})
                stats = v.get("statistics", {})
                video = v.get("video", {})
                cover = video.get("origin_cover", {}).get("url_list", [None])[0] or \
                        video.get("cover", {}).get("url_list", [None])[0] or ""

                ads.append({
                    "aweme_id": v.get("aweme_id", ""),
                    "author_id": author.get("uid", ""),
                    "author_username": author.get("uniqueId", ""),
                    "author_nickname": author.get("nickname", ""),
                    "author_avatar": author.get("avatar_thumb", {}).get("url_list", [None])[0] or "",
                    "description": v.get("desc", ""),
                    "play_count": stats.get("play_count", 0),
                    "like_count": stats.get("digg_count", 0),
                    "comment_count": stats.get("comment_count", 0),
                    "share_count": stats.get("share_count", 0),
                    "create_time": v.get("create_time", 0),
                    "cover_url": cover,
                    "is_ad": is_ad,
                    "branded_content": branded,
                    "ad_source": commerce.get("ad_source", 0),
                    "duration": video.get("duration", 0),
                    "hashtags": [h.get("hashtag_name", "") for h in v.get("text_extra", []) if h.get("hashtag_name")],
                })

            return {
                "success": True,
                "ads": ads,
                "total_results": len(all_items),
                "ads_count": len(ads),
                "credits_remaining": data.get("credits_remaining"),
            }
        except Exception as e:
            logger.error(f"Error parsing TikTok ads search for {query}: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Credits
    # =========================================================================

    async def get_credits(self) -> Optional[int]:
        """Get remaining API credits from any lightweight call."""
        # Use a minimal request to check credits
        data = await self._get("/v1/tiktok/profile", {"handle": "tiktok"})
        return data.get("credits_remaining")


# Singleton instance
scrapecreators = ScrapeCreatorsAPI()

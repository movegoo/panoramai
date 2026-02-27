"""
Scheduler service for automated data collection.
Uses APScheduler for daily background jobs.
"""
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from database import SessionLocal, Competitor, AppData, InstagramData, TikTokData, YouTubeData, Ad, SnapchatData, GoogleTrendsData, GoogleNewsArticle
from core.config import settings
from core.trends import parse_download_count

logger = logging.getLogger(__name__)


class DataCollectionScheduler:
    """Handles scheduled data collection from all sources."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()

    def _setup_jobs(self):
        """Configure all scheduled jobs."""
        # Daily collection
        self.scheduler.add_job(
            self.daily_data_collection,
            CronTrigger(hour=settings.SCHEDULER_HOUR, minute=settings.SCHEDULER_MINUTE),
            id="daily_collection",
            name="Daily Data Collection",
            replace_existing=True
        )

        # Daily ad snapshots + signal detection (30 min after collection)
        self.scheduler.add_job(
            self.daily_snapshots_and_signals,
            CronTrigger(hour=settings.SCHEDULER_HOUR, minute=settings.SCHEDULER_MINUTE + 30),
            id="daily_signals",
            name="Daily Snapshots & Signal Detection",
            replace_existing=True
        )

        # Daily creative analysis (1h after collection, after signals)
        self.scheduler.add_job(
            self.daily_creative_analysis,
            CronTrigger(hour=settings.SCHEDULER_HOUR + 1, minute=settings.SCHEDULER_MINUTE),
            id="daily_creative_analysis",
            name="Daily Creative Analysis",
            replace_existing=True
        )

        # Daily social content collection + AI analysis (1h30 after collection)
        self.scheduler.add_job(
            self.daily_social_analysis,
            CronTrigger(hour=settings.SCHEDULER_HOUR + 1, minute=settings.SCHEDULER_MINUTE + 30),
            id="daily_social_analysis",
            name="Daily Social Content Analysis",
            replace_existing=True
        )

        # Daily SEO SERP tracking (2h after collection)
        self.scheduler.add_job(
            self.daily_seo_tracking,
            CronTrigger(hour=settings.SCHEDULER_HOUR + 2, minute=settings.SCHEDULER_MINUTE),
            id="daily_seo_tracking",
            name="Daily SEO SERP Tracking",
            replace_existing=True
        )

        # Daily GEO tracking (2h30 after collection)
        self.scheduler.add_job(
            self.daily_geo_tracking,
            CronTrigger(hour=settings.SCHEDULER_HOUR + 2, minute=settings.SCHEDULER_MINUTE + 30),
            id="daily_geo_tracking",
            name="Daily GEO Tracking",
            replace_existing=True
        )

        # Daily VGEO analysis (3h after collection)
        self.scheduler.add_job(
            self.daily_vgeo_analysis,
            CronTrigger(hour=settings.SCHEDULER_HOUR + 3, minute=settings.SCHEDULER_MINUTE),
            id="daily_vgeo_analysis",
            name="Daily VGEO Analysis",
            replace_existing=True
        )

        # Daily ASO analysis (3h30 after collection)
        self.scheduler.add_job(
            self.daily_aso_analysis,
            CronTrigger(hour=settings.SCHEDULER_HOUR + 3, minute=settings.SCHEDULER_MINUTE + 30),
            id="daily_aso_analysis",
            name="Daily ASO Analysis",
            replace_existing=True
        )

        # Daily Google Trends (4h after collection)
        self.scheduler.add_job(
            self.daily_google_trends,
            CronTrigger(hour=settings.SCHEDULER_HOUR + 4, minute=settings.SCHEDULER_MINUTE),
            id="daily_google_trends",
            name="Daily Google Trends",
            replace_existing=True
        )

        # Daily Google News (4h30 after collection)
        self.scheduler.add_job(
            self.daily_google_news,
            CronTrigger(hour=settings.SCHEDULER_HOUR + 4, minute=settings.SCHEDULER_MINUTE + 30),
            id="daily_google_news",
            name="Daily Google News",
            replace_existing=True
        )

        # Weekly market data refresh (Sundays 3 AM)
        self.scheduler.add_job(
            self.weekly_market_data_refresh,
            CronTrigger(day_of_week="sun", hour=3, minute=0),
            id="weekly_market_refresh",
            name="Weekly Market Data Refresh",
            replace_existing=True
        )

        # Monthly Meta token refresh (1st of each month at 4 AM)
        self.scheduler.add_job(
            self.monthly_meta_token_refresh,
            CronTrigger(day=1, hour=4, minute=0),
            id="monthly_meta_token_refresh",
            name="Monthly Meta Token Refresh",
            replace_existing=True
        )

    async def start(self):
        """Start the scheduler."""
        if settings.SCHEDULER_ENABLED:
            self.scheduler.start()
            logger.info(
                f"Scheduler started. Daily collection at "
                f"{settings.SCHEDULER_HOUR:02d}:{settings.SCHEDULER_MINUTE:02d}"
            )
        else:
            logger.info("Scheduler disabled via SCHEDULER_ENABLED=false")

    async def stop(self):
        """Stop the scheduler gracefully."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("Scheduler stopped")

    async def daily_data_collection(self):
        """Run all daily data collection tasks."""
        logger.info(f"Starting daily data collection at {datetime.utcnow()}")

        db = SessionLocal()
        try:
            competitors = (
                db.query(Competitor)
                .filter(Competitor.is_active == True)
                .all()
            )

            for competitor in competitors:
                await self._fetch_competitor_data(db, competitor)

            logger.info(f"Daily collection completed for {len(competitors)} competitors")

            # Enrich payer/beneficiary via SearchAPI.io (if configured)
            await self._enrich_payers_searchapi(db, competitors)

            # Enrich EU transparency data (age/gender/reach) for Meta ads
            await self._enrich_transparency(db)
        except Exception as e:
            logger.error(f"Error in daily data collection: {e}")
        finally:
            db.close()

    async def _fetch_competitor_data(self, db: Session, competitor: Competitor):
        """Fetch all data sources for a single competitor."""
        name = competitor.name

        # Facebook/Instagram ads
        await self._fetch_ads(db, competitor, name)

        if competitor.playstore_app_id:
            await self._fetch_playstore(db, competitor, name)

        if competitor.appstore_app_id:
            await self._fetch_appstore(db, competitor, name)

        if competitor.instagram_username:
            await self._fetch_instagram(db, competitor, name)

        if competitor.tiktok_username:
            await self._fetch_tiktok(db, competitor, name)

        if competitor.youtube_channel_id:
            await self._fetch_youtube(db, competitor, name)

        # Snapchat profile (via username)
        if competitor.snapchat_username:
            await self._fetch_snapchat_profile(db, competitor, name)

        # Snapchat Ads (via entity name)
        if competitor.snapchat_entity_name:
            await self._fetch_snapchat(db, competitor, name)

        # Google Ads (via domain)
        if competitor.website:
            await self._fetch_google_ads(db, competitor, name)

    async def _fetch_ads(self, db: Session, competitor: Competitor, name: str):
        """Fetch Facebook/Instagram ads from Ad Library.
        Primary: Meta Ad Library API (free, official).
        Fallback: ScrapeCreators (paid).
        """
        try:
            from routers.facebook import _name_matches, _parse_date
            from database import Ad
            import json

            page_id = competitor.facebook_page_id
            new_count = 0

            # ── Primary: Meta Ad Library API ──
            if page_id:
                try:
                    from services.meta_ad_library import meta_ad_library
                    if meta_ad_library.is_configured:
                        meta_ads = await meta_ad_library.get_active_ads(page_id, country="FR")
                        if meta_ads:
                            new_count = self._store_meta_api_ads(db, competitor, meta_ads, _parse_date)
                            if new_count >= 0:
                                logger.info(f"Ads: {new_count} new ads via Meta API for {name}")
                                return
                except Exception as e:
                    logger.warning(f"Meta API failed for {name}, falling back to ScrapeCreators: {e}")

            # ── Fallback: ScrapeCreators ──
            try:
                from services.scrapecreators import scrapecreators

                ads_list = []
                use_page_id = False
                if page_id:
                    cursor = None
                    for _ in range(30):
                        result = await scrapecreators.fetch_facebook_company_ads(page_id=page_id, cursor=cursor)
                        if not result.get("success"):
                            break
                        batch = result.get("ads", [])
                        ads_list.extend(batch)
                        cursor = result.get("cursor")
                        if not cursor or not batch:
                            break
                    if ads_list:
                        use_page_id = True

                if not ads_list:
                    result = await scrapecreators.search_facebook_ads(
                        company_name=name, country="FR", limit=50
                    )
                    if not result.get("success"):
                        return
                    ads_list = result.get("ads", [])

                for ad in ads_list:
                    ad_id = str(ad.get("ad_archive_id", ""))
                    if not ad_id:
                        continue
                    snapshot = ad.get("snapshot", {})
                    page_name_val = snapshot.get("page_name", "") or ad.get("page_name", "")
                    if not use_page_id and not _name_matches(name, page_name_val):
                        continue
                    if db.query(Ad).filter(Ad.ad_id == ad_id).first():
                        continue

                    cards = snapshot.get("cards", [])
                    first_card = cards[0] if cards else {}
                    start_date = _parse_date(ad.get("start_date_string") or ad.get("start_date"))
                    end_date = _parse_date(ad.get("end_date_string") or ad.get("end_date"))
                    pub_platforms = ad.get("publisher_platform", [])
                    if not isinstance(pub_platforms, list):
                        pub_platforms = [pub_platforms] if pub_platforms else []

                    new_ad = Ad(
                        competitor_id=competitor.id,
                        ad_id=ad_id,
                        platform="instagram" if any("INSTAGRAM" in str(p).upper() for p in pub_platforms) else "facebook",
                        creative_url=first_card.get("original_image_url") or first_card.get("resized_image_url") or "",
                        ad_text=first_card.get("body") or snapshot.get("body", {}).get("text", "") or "",
                        cta=first_card.get("cta_text") or snapshot.get("cta_text", ""),
                        start_date=start_date,
                        end_date=end_date,
                        is_active=ad.get("is_active", not bool(end_date)),
                        page_name=page_name_val or None,
                        ad_library_url=ad.get("url", "") or None,
                    )
                    db.add(new_ad)
                    new_count += 1

                if new_count:
                    db.commit()
                    logger.info(f"Ads: {new_count} new ads via ScrapeCreators for {name}")
            except Exception as e:
                logger.error(f"ScrapeCreators fallback failed for {name}: {e}")
        except Exception as e:
            logger.error(f"Ads fetch failed for {name}: {e}")

    @staticmethod
    def _store_meta_api_ads(db: Session, competitor, meta_ads: list[dict], _parse_date) -> int:
        """Map Meta Ad Library API response to Ad model and store in DB.
        Returns count of new ads stored.
        """
        from database import Ad
        import json

        new_count = 0
        for ad in meta_ads:
            ad_id = str(ad.get("id", ""))
            if not ad_id:
                continue
            if db.query(Ad).filter(Ad.ad_id == ad_id).first():
                continue

            # Determine platform from publisher_platforms
            pub_platforms = ad.get("publisher_platforms", [])
            platform = "facebook"
            if pub_platforms:
                if any("instagram" in str(p).lower() for p in pub_platforms):
                    platform = "instagram"

            # Parse dates
            start_date = _parse_date(ad.get("ad_delivery_start_time"))
            end_date = _parse_date(ad.get("ad_delivery_stop_time"))

            # Extract creative text
            bodies = ad.get("ad_creative_bodies", [])
            ad_text = bodies[0] if bodies else ""

            # Extract title
            titles = ad.get("ad_creative_link_titles", [])
            title = titles[0][:1000] if titles else None

            # Extract link description
            descriptions = ad.get("ad_creative_link_descriptions", [])
            link_description = descriptions[0] if descriptions else None

            # Extract impressions range
            impressions = ad.get("impressions", {})
            impressions_min = None
            impressions_max = None
            if isinstance(impressions, dict):
                try:
                    impressions_min = int(impressions.get("lower_bound", 0)) if impressions.get("lower_bound") else None
                    impressions_max = int(impressions.get("upper_bound", 0)) if impressions.get("upper_bound") else None
                except (ValueError, TypeError):
                    pass

            # Extract spend range
            spend = ad.get("spend", {})
            spend_min = None
            spend_max = None
            if isinstance(spend, dict):
                try:
                    spend_min = float(spend.get("lower_bound", 0)) if spend.get("lower_bound") else None
                    spend_max = float(spend.get("upper_bound", 0)) if spend.get("upper_bound") else None
                except (ValueError, TypeError):
                    pass

            # Extract payer/beneficiary
            bp_list = ad.get("beneficiary_payers", [])
            payer = None
            beneficiary = None
            if bp_list:
                payer = bp_list[0].get("payer")
                beneficiary = bp_list[0].get("beneficiary")

            new_ad = Ad(
                competitor_id=competitor.id,
                ad_id=ad_id,
                platform=platform,
                creative_url="",  # Not available via Meta API
                ad_text=ad_text,
                title=title,
                link_description=link_description,
                cta="",  # Not available via Meta API
                start_date=start_date,
                end_date=end_date,
                is_active=not bool(end_date),
                page_id=ad.get("page_id"),
                page_name=ad.get("page_name"),
                ad_library_url=ad.get("ad_snapshot_url") or None,
                publisher_platforms=json.dumps(pub_platforms) if pub_platforms else None,
                eu_total_reach=ad.get("eu_total_reach") or None,
                impressions_min=impressions_min,
                impressions_max=impressions_max,
                estimated_spend_min=spend_min,
                estimated_spend_max=spend_max,
                payer=payer,
                beneficiary=beneficiary,
                byline=ad.get("bylines", ""),
            )
            db.add(new_ad)
            new_count += 1

        if new_count:
            db.commit()
        return new_count

    async def _fetch_snapchat(self, db: Session, competitor: Competitor, name: str):
        """Fetch Snapchat ads via Apify."""
        try:
            from services.apify_snapchat import apify_snapchat
            import json

            entity_name = competitor.snapchat_entity_name
            result = await apify_snapchat.search_snapchat_ads(query=entity_name)

            if not result.get("success"):
                logger.warning(f"Snapchat fetch returned no data for {name}: {result.get('error')}")
                return

            new_count = 0
            for ad_data in result.get("ads", []):
                ad_id = ad_data.get("snap_id", "")
                if not ad_id:
                    continue
                if db.query(Ad).filter(Ad.ad_id == ad_id).first():
                    continue

                new_ad = Ad(
                    competitor_id=competitor.id,
                    ad_id=ad_id,
                    platform="snapchat",
                    creative_url=ad_data.get("creative_url", ""),
                    ad_text=ad_data.get("ad_text", ""),
                    title=ad_data.get("title", "")[:200] if ad_data.get("title") else None,
                    start_date=ad_data.get("start_date"),
                    is_active=ad_data.get("is_active", False),
                    impressions_min=ad_data.get("impressions", 0),
                    impressions_max=ad_data.get("impressions", 0),
                    publisher_platforms=json.dumps(["SNAPCHAT"]),
                    page_name=ad_data.get("page_name", ""),
                    display_format=ad_data.get("display_format", "SNAP"),
                    ad_library_url="https://adsgallery.snap.com/",
                )
                db.add(new_ad)
                new_count += 1

            if new_count:
                db.commit()
                logger.info(f"Snapchat: {new_count} new ads stored for {name}")
        except Exception as e:
            logger.error(f"Snapchat fetch failed for {name}: {e}")

    async def _fetch_google_ads(self, db: Session, competitor: Competitor, name: str):
        """Fetch Google Ads from Transparency Center."""
        try:
            from routers.google_ads import _fetch_and_store_google_ads, _extract_domain
            domain = _extract_domain(competitor.website)
            if domain:
                new, updated, fetched = await _fetch_and_store_google_ads(
                    competitor_id=competitor.id, domain=domain, country="FR", db=db
                )
                if new > 0:
                    logger.info(f"Google Ads: {new} new, {updated} updated for {name}")
        except Exception as e:
            logger.error(f"Google Ads fetch failed for {name}: {e}")

    async def _enrich_transparency(self, db: Session):
        """Enrich Meta ads with EU transparency data (age/gender/reach).
        Primary: SearchAPI ad_details (via meta_ad_library.enrich_ad_details).
        Fallback: ScrapeCreators get_facebook_ad_detail.
        """
        try:
            import asyncio
            import json
            from database import Ad

            meta_platforms = ["facebook", "instagram", "messenger", "audience_network", "meta",
                              "FACEBOOK", "INSTAGRAM", "MESSENGER", "AUDIENCE_NETWORK", "META"]

            # Get ads missing transparency data (max 100 per run)
            ads_to_enrich = db.query(Ad).filter(
                Ad.eu_total_reach.is_(None),
                Ad.platform.in_(meta_platforms),
            ).limit(100).all()

            if not ads_to_enrich:
                return

            # Try to use SearchAPI via meta_ad_library (primary)
            from services.meta_ad_library import meta_ad_library
            use_searchapi = bool(meta_ad_library.searchapi_key)

            async def _enrich_one(ad):
                try:
                    # Primary: SearchAPI ad_details
                    if use_searchapi:
                        detail = await meta_ad_library.enrich_ad_details(ad.ad_id)
                        if detail:
                            ad.eu_total_reach = detail.get("eu_total_reach") or 0
                            payer = detail.get("payer")
                            beneficiary_val = detail.get("beneficiary")
                            if payer:
                                ad.payer = payer
                            if beneficiary_val:
                                ad.beneficiary = beneficiary_val
                            age_gender = detail.get("age_gender_data", [])
                            if age_gender:
                                ad.age_country_gender_reach = json.dumps(age_gender)
                            loc = detail.get("location_data", [])
                            if loc:
                                ad.location_audience = json.dumps(loc)
                            return True

                    # Fallback: ScrapeCreators
                    from services.scrapecreators import scrapecreators
                    sc_detail = await scrapecreators.get_facebook_ad_detail(ad.ad_id)
                    if not sc_detail.get("success"):
                        ad.eu_total_reach = 0
                        return False
                    ad.age_min = sc_detail.get("age_min")
                    ad.age_max = sc_detail.get("age_max")
                    ad.gender_audience = sc_detail.get("gender_audience")
                    ad.eu_total_reach = sc_detail.get("eu_total_reach") or 0
                    loc = sc_detail.get("location_audience", [])
                    if loc:
                        ad.location_audience = json.dumps(loc)
                    breakdown = sc_detail.get("age_country_gender_reach_breakdown", [])
                    if breakdown:
                        ad.age_country_gender_reach = json.dumps(breakdown)
                    byline = sc_detail.get("byline")
                    if byline:
                        ad.byline = byline
                    payer = sc_detail.get("payer")
                    beneficiary_val = sc_detail.get("beneficiary")
                    if payer:
                        ad.payer = payer
                    if beneficiary_val:
                        ad.beneficiary = beneficiary_val
                    return True
                except Exception as e:
                    logger.error(f"Transparency enrichment failed for ad {ad.ad_id}: {e}")
                    ad.eu_total_reach = 0
                    return False

            # Process in batches of 10
            enriched = 0
            errors = 0
            source = "SearchAPI" if use_searchapi else "ScrapeCreators"
            for i in range(0, len(ads_to_enrich), 10):
                batch = ads_to_enrich[i:i + 10]
                results = await asyncio.gather(*[_enrich_one(ad) for ad in batch])
                enriched += sum(1 for r in results if r)
                errors += sum(1 for r in results if not r)
                db.commit()

            logger.info(f"Transparency ({source}): enriched {enriched}/{len(ads_to_enrich)} ads ({errors} errors)")
        except Exception as e:
            logger.error(f"Transparency enrichment failed: {e}")

    async def _enrich_payers_searchapi(self, db: Session, competitors):
        """Enrich new Meta ads with payer/beneficiary via SearchAPI.io."""
        try:
            from services.searchapi import searchapi
            if not searchapi.is_configured:
                return

            from database import Ad
            comp_ids = [c.id for c in competitors]

            # Only enrich ads that have been through ScrapeCreators enrichment but lack payer
            ads = db.query(Ad).filter(
                Ad.payer.is_(None),
                Ad.eu_total_reach.isnot(None),
                Ad.platform.in_(["facebook", "instagram"]),
                Ad.competitor_id.in_(comp_ids),
            ).all()

            if not ads:
                return

            enriched = 0
            for ad in ads:
                result = await searchapi.get_ad_details(ad.ad_id)
                if not result.get("success"):
                    continue
                payer = result.get("payer")
                beneficiary = result.get("beneficiary")
                if payer:
                    ad.payer = payer
                if beneficiary:
                    ad.beneficiary = beneficiary
                if payer or beneficiary:
                    enriched += 1

            if enriched:
                db.commit()
                logger.info(f"SearchAPI: enriched {enriched}/{len(ads)} ads with payer/beneficiary")
        except Exception as e:
            logger.error(f"SearchAPI payer enrichment failed: {e}")

    async def _fetch_playstore(self, db: Session, competitor: Competitor, name: str):
        """Fetch Play Store data."""
        try:
            from routers.playstore import fetch_playstore_app

            result = fetch_playstore_app(competitor.playstore_app_id)
            if result.get("success"):
                app_data = AppData(
                    competitor_id=competitor.id,
                    store="playstore",
                    app_id=competitor.playstore_app_id,
                    app_name=result["app_name"],
                    rating=result["rating"],
                    reviews_count=result["reviews_count"],
                    downloads=result["downloads"],
                    downloads_numeric=parse_download_count(result["downloads"]),
                    version=result["version"],
                    last_updated=result["last_updated"],
                    description=result["description"],
                    changelog=result["changelog"]
                )
                db.add(app_data)
                db.commit()
                logger.info(f"Play Store data fetched for {name}")
        except Exception as e:
            logger.error(f"Play Store fetch failed for {name}: {e}")

    async def _fetch_appstore(self, db: Session, competitor: Competitor, name: str):
        """Fetch App Store data."""
        try:
            from routers.appstore import fetch_appstore_app

            result = await fetch_appstore_app(competitor.appstore_app_id)
            if result.get("success"):
                app_data = AppData(
                    competitor_id=competitor.id,
                    store="appstore",
                    app_id=competitor.appstore_app_id,
                    app_name=result["app_name"],
                    rating=result["rating"],
                    reviews_count=result["reviews_count"],
                    downloads=None,
                    version=result["version"],
                    last_updated=result["last_updated"],
                    description=result["description"],
                    changelog=result["changelog"]
                )
                db.add(app_data)
                db.commit()
                logger.info(f"App Store data fetched for {name}")
        except Exception as e:
            logger.error(f"App Store fetch failed for {name}: {e}")

    async def _fetch_instagram(self, db: Session, competitor: Competitor, name: str):
        """Fetch Instagram data via FallbackChain (ScrapeCreators → Apify)."""
        try:
            from services.scrapecreators import scrapecreators
            from services.fallback import FallbackChain

            async def _sc():
                r = await scrapecreators.fetch_instagram_profile(competitor.instagram_username)
                if not r.get("success"):
                    raise Exception(r.get("error", "failed"))
                return r

            chain = FallbackChain([("scrapecreators", _sc)])
            result = await chain.execute()

            if result.success:
                d = result.data
                ig_data = InstagramData(
                    competitor_id=competitor.id,
                    followers=d.get("followers", 0),
                    following=d.get("following", 0),
                    posts_count=d.get("posts_count", 0),
                    avg_likes=d.get("avg_likes", 0),
                    avg_comments=d.get("avg_comments", 0),
                    engagement_rate=d.get("engagement_rate", 0),
                    bio=d.get("bio")
                )
                db.add(ig_data)
                db.commit()
                src = result.source + (f" (+{','.join(result.complemented_from)})" if result.complemented_from else "")
                logger.info(f"Instagram data fetched for {name} via {src}")
            else:
                logger.warning(f"Instagram fetch returned no data for {name}: {result.errors}")
        except Exception as e:
            logger.error(f"Instagram fetch failed for {name}: {e}")

    async def _fetch_tiktok(self, db: Session, competitor: Competitor, name: str):
        """Fetch TikTok data via FallbackChain."""
        try:
            from services.tiktok_scraper import tiktok_scraper
            from services.fallback import FallbackChain

            async def _sc():
                r = await tiktok_scraper.fetch_profile(competitor.tiktok_username)
                if not r.get("success"):
                    raise Exception(r.get("error", "failed"))
                return r

            chain = FallbackChain([("tiktok_scraper", _sc)])
            result = await chain.execute()

            if result.success:
                d = result.data
                tt_data = TikTokData(
                    competitor_id=competitor.id,
                    username=competitor.tiktok_username,
                    followers=d.get("followers", 0),
                    following=d.get("following", 0),
                    likes=d.get("likes", 0),
                    videos_count=d.get("videos_count", 0),
                    bio=d.get("bio"),
                    verified=d.get("verified", False)
                )
                db.add(tt_data)
                db.commit()
                logger.info(f"TikTok data fetched for {name} via {result.source}")
            else:
                logger.warning(f"TikTok fetch returned no data for {name}: {result.errors}")
        except Exception as e:
            logger.error(f"TikTok fetch failed for {name}: {e}")

    async def _fetch_youtube(self, db: Session, competitor: Competitor, name: str):
        """Fetch YouTube data."""
        try:
            from services.youtube_api import youtube_api

            result = await youtube_api.get_channel_analytics(competitor.youtube_channel_id)
            if result.get("success"):
                analytics = result.get("analytics", {})
                yt_data = YouTubeData(
                    competitor_id=competitor.id,
                    channel_id=competitor.youtube_channel_id,
                    channel_name=result.get("channel_name"),
                    subscribers=result.get("subscribers", 0),
                    total_views=result.get("total_views", 0),
                    videos_count=result.get("videos_count", 0),
                    avg_views=analytics.get("avg_views", 0),
                    avg_likes=analytics.get("avg_likes", 0),
                    avg_comments=analytics.get("avg_comments", 0),
                    engagement_rate=analytics.get("engagement_rate", 0),
                    description=result.get("description")
                )
                db.add(yt_data)
                db.commit()
                logger.info(f"YouTube data fetched for {name}")
        except Exception as e:
            logger.error(f"YouTube fetch failed for {name}: {e}")

    async def _fetch_snapchat_profile(self, db: Session, competitor: Competitor, name: str):
        """Fetch Snapchat profile data via ScrapeCreators."""
        try:
            from services.scrapecreators import scrapecreators

            # Rate limit: skip if last fetch was less than 1 hour ago
            latest = (
                db.query(SnapchatData)
                .filter(SnapchatData.competitor_id == competitor.id)
                .order_by(SnapchatData.recorded_at.desc())
                .first()
            )
            if latest and (datetime.utcnow() - latest.recorded_at).total_seconds() < 3600:
                logger.debug(f"Snapchat profile: skipping {name} (fetched <1h ago)")
                return

            result = await scrapecreators.fetch_snapchat_profile(competitor.snapchat_username)
            if not result.get("success"):
                logger.warning(f"Snapchat profile fetch returned no data for {name}: {result.get('error')}")
                return

            snap_data = SnapchatData(
                competitor_id=competitor.id,
                subscribers=result.get("subscribers", 0),
                title=result.get("title", ""),
                story_count=result.get("story_count", 0),
                spotlight_count=result.get("spotlight_count", 0),
                total_views=result.get("total_views", 0),
                total_shares=result.get("total_shares", 0),
                total_comments=result.get("total_comments", 0),
                engagement_rate=result.get("engagement_rate", 0),
                profile_picture_url=result.get("profile_picture_url", ""),
            )
            db.add(snap_data)
            db.commit()
            logger.info(f"Snapchat profile fetched for {name}: {result.get('subscribers', 0)} subscribers")
        except Exception as e:
            logger.error(f"Snapchat profile fetch failed for {name}: {e}")

    async def daily_snapshots_and_signals(self):
        """Take ad snapshots and run signal detection after daily collection."""
        logger.info(f"Starting daily snapshots & signals at {datetime.utcnow()}")
        db = SessionLocal()
        try:
            from services.signals import snapshot_active_ads, detect_all_signals

            # 1. Snapshot active ads
            snap_count = snapshot_active_ads(db)
            logger.info(f"Ad snapshots complete: {snap_count} ads")

            # 2. Detect signals for all competitors
            signals = detect_all_signals(db)
            logger.info(f"Signal detection complete: {len(signals)} new signals")
        except Exception as e:
            logger.error(f"Snapshots & signals failed: {e}")
        finally:
            db.close()

    async def daily_creative_analysis(self):
        """Analyze all unanalyzed ad creatives automatically."""
        import asyncio
        import json

        logger.info(f"Starting daily creative analysis at {datetime.utcnow()}")
        db = SessionLocal()
        try:
            from services.creative_analyzer import creative_analyzer

            SKIP_URL_PATTERNS = ["googlesyndication.com", "2mdn.net", "doubleclick.net"]
            BATCH_SIZE = 50
            MAX_BATCHES = 500  # No artificial cap — process all unanalyzed ads
            MAX_TIME = 14400  # 4 hours max

            # Auto-reset previous failures (score=0) for retry
            failed = db.query(Ad).filter(
                Ad.creative_analyzed_at.isnot(None),
                Ad.creative_score == 0,
            ).all()
            for ad in failed:
                ad.creative_analyzed_at = None
                ad.creative_score = None
                ad.creative_analysis = None
            if failed:
                db.commit()
                logger.info(f"Creative analysis: reset {len(failed)} failed analyses for retry")

            total_analyzed = 0
            total_errors = 0
            start_time = asyncio.get_event_loop().time()

            for batch_num in range(MAX_BATCHES):
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= MAX_TIME:
                    logger.info(f"Creative analysis: time limit reached after {total_analyzed} ads")
                    break

                # Fetch next batch of unanalyzed ads (images OR text-only)
                from sqlalchemy import or_, func as sa_func
                candidates = db.query(Ad).filter(
                    Ad.creative_analyzed_at.is_(None),
                    or_(
                        (Ad.creative_url.isnot(None)) & (Ad.creative_url != ""),
                        (Ad.ad_text.isnot(None)) & (sa_func.length(Ad.ad_text) >= 10),
                    ),
                ).limit(BATCH_SIZE * 3).all()

                if not candidates:
                    break

                ads_to_analyze = []
                for ad in candidates:
                    fmt = (ad.display_format or "").upper()
                    url = ad.creative_url or ""
                    has_text = ad.ad_text and len(ad.ad_text.strip()) >= 10
                    # Skip VIDEO only if no ad text to analyze
                    if fmt == "VIDEO" and not has_text:
                        continue
                    if any(p in url for p in SKIP_URL_PATTERNS) and not has_text:
                        ad.creative_analyzed_at = datetime.utcnow()
                        ad.creative_score = 0
                        ad.creative_summary = "URL non analysable (réseau publicitaire)"
                        continue
                    if len(ads_to_analyze) < BATCH_SIZE:
                        ads_to_analyze.append(ad)
                db.commit()

                if not ads_to_analyze:
                    break

                for ad in ads_to_analyze:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed >= MAX_TIME:
                        break

                    try:
                        platform = "tiktok" if ad.platform == "tiktok" else "google" if ad.platform == "google" else "meta"
                        url = ad.creative_url or ""
                        # Facebook snapshot URLs are not real images — treat as text-only
                        is_snapshot = "facebook.com/ads/archive/render_ad" in url
                        has_image = url and not is_snapshot and not any(
                            p in url for p in SKIP_URL_PATTERNS
                        )
                        has_text = ad.ad_text and len(ad.ad_text.strip()) >= 10
                        if not has_image and has_text:
                            result = await asyncio.wait_for(
                                creative_analyzer.analyze_text_only(
                                    ad_text=ad.ad_text,
                                    platform=platform,
                                    ad_id=ad.ad_id or "",
                                ),
                                timeout=45,
                            )
                        else:
                            result = await asyncio.wait_for(
                                creative_analyzer.analyze_creative(
                                    creative_url=ad.creative_url,
                                    ad_text=ad.ad_text or "",
                                    platform=platform,
                                    ad_id=ad.ad_id or "",
                                ),
                                timeout=60,
                            )

                        if result:
                            ad.creative_analysis = json.dumps(result, ensure_ascii=False)
                            ad.creative_concept = result.get("concept", "")[:100]
                            ad.creative_hook = result.get("hook", "")[:500]
                            ad.creative_tone = result.get("tone", "")[:100]
                            ad.creative_text_overlay = result.get("text_overlay", "")
                            ad.creative_dominant_colors = json.dumps(result.get("dominant_colors", []))
                            ad.creative_has_product = result.get("has_product", False)
                            ad.creative_has_face = result.get("has_face", False)
                            ad.creative_has_logo = result.get("has_logo", False)
                            ad.creative_layout = result.get("layout", "")[:50]
                            ad.creative_cta_style = result.get("cta_style", "")[:50]
                            ad.creative_score = result.get("score", 0)
                            ad.creative_tags = json.dumps(result.get("tags", []), ensure_ascii=False)
                            ad.creative_summary = result.get("summary", "")
                            ad.product_category = result.get("product_category", "")[:100]
                            ad.product_subcategory = result.get("product_subcategory", "")[:100]
                            ad.ad_objective = result.get("ad_objective", "")[:50]
                            ad.creative_analyzed_at = datetime.utcnow()
                            total_analyzed += 1
                        else:
                            ad.creative_analyzed_at = datetime.utcnow()
                            ad.creative_score = 0
                            total_errors += 1

                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout analyzing ad {ad.ad_id}")
                        total_errors += 1
                    except Exception as e:
                        logger.error(f"Error analyzing ad {ad.ad_id}: {e}")
                        ad.creative_analyzed_at = datetime.utcnow()
                        ad.creative_score = 0
                        total_errors += 1

                    await asyncio.sleep(1.0)

                db.commit()
                logger.info(f"Creative analysis batch {batch_num + 1}: {total_analyzed} analyzed, {total_errors} errors")

            # Count remaining
            remaining = db.query(Ad).filter(Ad.creative_analyzed_at.is_(None)).count()
            logger.info(f"Daily creative analysis complete: {total_analyzed} analyzed, {total_errors} errors, {remaining} remaining")

        except Exception as e:
            logger.error(f"Daily creative analysis failed: {e}")
        finally:
            db.close()

    async def daily_social_analysis(self):
        """Collect social posts (TikTok, YouTube, Instagram) + AI analysis for all competitors."""
        import asyncio
        logger.info(f"Starting daily social content analysis at {datetime.utcnow()}")

        db = SessionLocal()
        try:
            from database import SocialPost, AdvertiserCompetitor
            from services.scrapecreators import scrapecreators
            from services.social_content_analyzer import social_content_analyzer

            competitors = db.query(Competitor).filter(Competitor.is_active == True).all()
            total_new = 0
            total_analyzed = 0

            # ── Phase 1: Collect posts ──
            for comp in competitors:
                try:
                    # TikTok
                    if comp.tiktok_username:
                        data = await scrapecreators.fetch_tiktok_videos(comp.tiktok_username, limit=10)
                        if data.get("success"):
                            for video in data.get("videos", []):
                                post_id = f"tt_{video.get('id', '')}"
                                if not post_id or post_id == "tt_":
                                    continue
                                if db.query(SocialPost).filter(SocialPost.post_id == post_id).first():
                                    continue
                                published = None
                                ct = video.get("create_time")
                                if ct and isinstance(ct, (int, float)):
                                    try:
                                        published = datetime.utcfromtimestamp(ct)
                                    except (ValueError, OSError):
                                        pass
                                db.add(SocialPost(
                                    post_id=post_id, competitor_id=comp.id, platform="tiktok",
                                    title="", description=video.get("description", "")[:2000],
                                    url=f"https://tiktok.com/@{comp.tiktok_username}/video/{video.get('id', '')}",
                                    published_at=published,
                                    views=video.get("views", 0) or 0, likes=video.get("likes", 0) or 0,
                                    comments=video.get("comments", 0) or 0, shares=video.get("shares", 0) or 0,
                                    collected_at=datetime.utcnow(),
                                ))
                                total_new += 1
                        await asyncio.sleep(0.3)

                    # YouTube
                    if comp.youtube_channel_id:
                        data = await scrapecreators.fetch_youtube_videos(channel_id=comp.youtube_channel_id, limit=10)
                        if data.get("success"):
                            for video in data.get("videos", []):
                                vid = video.get("video_id", "")
                                post_id = f"yt_{vid}"
                                if not vid:
                                    continue
                                if db.query(SocialPost).filter(SocialPost.post_id == post_id).first():
                                    continue
                                db.add(SocialPost(
                                    post_id=post_id, competitor_id=comp.id, platform="youtube",
                                    title=video.get("title", "")[:1000], description=video.get("description", "")[:2000],
                                    url=f"https://youtube.com/watch?v={vid}",
                                    thumbnail_url=video.get("thumbnail_url", ""),
                                    duration=video.get("duration", ""),
                                    views=video.get("views", 0) or 0, likes=video.get("likes", 0) or 0,
                                    comments=video.get("comments", 0) or 0,
                                    collected_at=datetime.utcnow(),
                                ))
                                total_new += 1
                        await asyncio.sleep(0.3)

                    # Instagram
                    if comp.instagram_username:
                        data = await scrapecreators._get("/v1/instagram/profile", {"handle": comp.instagram_username.lstrip("@")})
                        if data.get("success"):
                            user_data = data.get("data", {}).get("user", {})
                            edges = user_data.get("edge_owner_to_timeline_media", {}).get("edges", [])
                            for edge in edges[:10]:
                                node = edge.get("node", {})
                                ig_id = node.get("id", "")
                                post_id = f"ig_{ig_id}"
                                if not ig_id:
                                    continue
                                if db.query(SocialPost).filter(SocialPost.post_id == post_id).first():
                                    continue
                                caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
                                caption = caption_edges[0].get("node", {}).get("text", "") if caption_edges else ""
                                published = None
                                ts = node.get("taken_at_timestamp")
                                if ts:
                                    try:
                                        published = datetime.utcfromtimestamp(ts)
                                    except (ValueError, OSError):
                                        pass
                                shortcode = node.get("shortcode", "")
                                thumbnail = node.get("thumbnail_src", "") or node.get("display_url", "")
                                db.add(SocialPost(
                                    post_id=post_id, competitor_id=comp.id, platform="instagram",
                                    title="", description=caption[:2000],
                                    url=f"https://instagram.com/p/{shortcode}/" if shortcode else "",
                                    thumbnail_url=thumbnail, published_at=published,
                                    views=node.get("video_view_count", 0) or 0,
                                    likes=node.get("edge_liked_by", {}).get("count", 0) or 0,
                                    comments=node.get("edge_media_to_comment", {}).get("count", 0) or 0,
                                    collected_at=datetime.utcnow(),
                                ))
                                total_new += 1
                        await asyncio.sleep(0.3)

                except Exception as e:
                    logger.error(f"Social collect error for {comp.name}: {e}")

            db.commit()
            logger.info(f"Social collection done: {total_new} new posts from {len(competitors)} competitors")

            # ── Phase 2: AI analysis on unanalyzed posts ──
            # First reset previous failures (analyzed but score=0 = failed)
            failed = db.query(SocialPost).filter(
                SocialPost.content_analyzed_at.isnot(None),
                SocialPost.content_engagement_score == 0,
            ).all()
            for post in failed:
                post.content_analyzed_at = None
                post.content_engagement_score = None
                post.content_analysis = None
            if failed:
                db.commit()
                logger.info(f"Reset {len(failed)} failed social analyses for retry")

            unanalyzed = db.query(SocialPost).filter(SocialPost.content_analyzed_at.is_(None)).all()
            comp_names = {}
            for post in unanalyzed:
                if post.competitor_id not in comp_names:
                    comp = db.query(Competitor).get(post.competitor_id)
                    comp_names[post.competitor_id] = comp.name if comp else ""

            for post in unanalyzed:
                try:
                    result = await asyncio.wait_for(
                        social_content_analyzer.analyze_content(
                            platform=post.platform,
                            title=post.title or "",
                            description=post.description or "",
                            thumbnail_url=post.thumbnail_url or "",
                            views=post.views or 0,
                            likes=post.likes or 0,
                            comments=post.comments or 0,
                            shares=post.shares or 0,
                            competitor_name=comp_names.get(post.competitor_id, ""),
                        ),
                        timeout=30,
                    )
                    if result:
                        import json
                        post.content_analysis = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else result
                        post.content_theme = result.get("theme", "") if isinstance(result, dict) else ""
                        post.content_tone = result.get("tone", "") if isinstance(result, dict) else ""
                        post.content_engagement_score = result.get("engagement_score", 0) if isinstance(result, dict) else 0
                        post.content_topics = json.dumps(result.get("content_topics", []), ensure_ascii=False) if isinstance(result, dict) else "[]"
                        post.content_products = json.dumps(result.get("content_products", []), ensure_ascii=False) if isinstance(result, dict) else "[]"
                        post.content_analyzed_at = datetime.utcnow()
                        total_analyzed += 1
                        if total_analyzed % 10 == 0:
                            db.commit()
                except Exception as e:
                    logger.error(f"Social analysis error for post {post.post_id}: {e}")
                    post.content_analyzed_at = datetime.utcnow()
                    post.content_engagement_score = 0

            db.commit()
            logger.info(f"Social analysis done: {total_analyzed} posts analyzed")

        except Exception as e:
            logger.error(f"Daily social analysis failed: {e}")
        finally:
            db.close()

    async def daily_seo_tracking(self):
        """Run SEO SERP tracking for ALL active advertisers automatically."""
        import asyncio
        logger.info(f"Starting daily SEO tracking at {datetime.utcnow()}")

        db = SessionLocal()
        try:
            from database import Advertiser, AdvertiserCompetitor, SerpResult
            from routers.seo import _get_sector_keywords, _build_domain_map, _match_competitor, _extract_domain
            from services.scrapecreators import scrapecreators

            advertisers = db.query(Advertiser).filter(Advertiser.is_active == True).all()
            total_results = 0

            for adv in advertisers:
                competitors = (
                    db.query(Competitor)
                    .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
                    .filter(AdvertiserCompetitor.advertiser_id == adv.id, Competitor.is_active == True)
                    .all()
                )
                if not competitors:
                    continue

                sector = adv.sector or "supermarche"
                keywords = _get_sector_keywords(sector)
                domain_map = _build_domain_map(competitors)
                valid_ids = {c.id for c in competitors}
                now = datetime.utcnow()
                adv_results = 0

                logger.info(f"SEO tracking: {adv.company_name} ({sector}) — {len(keywords)} keywords, {len(competitors)} competitors")

                for i, keyword in enumerate(keywords):
                    try:
                        data = await scrapecreators.search_google(keyword, country="FR", limit=10)
                        if not data.get("success"):
                            continue

                        for pos_idx, result in enumerate(data.get("results", [])[:10], start=1):
                            url = result.get("url", "")
                            domain = _extract_domain(url)
                            cid = _match_competitor(domain, domain_map)
                            if cid and cid not in valid_ids:
                                cid = None

                            serp = SerpResult(
                                user_id=None,
                                advertiser_id=adv.id,
                                keyword=keyword,
                                position=pos_idx,
                                competitor_id=cid,
                                title=result.get("title", "")[:1000],
                                url=url[:1000],
                                snippet=result.get("description", ""),
                                domain=domain,
                                recorded_at=now,
                            )
                            db.add(serp)
                            adv_results += 1

                    except Exception as e:
                        logger.error(f"SEO track error for '{keyword}' ({adv.company_name}): {e}")

                    if i < len(keywords) - 1:
                        await asyncio.sleep(0.3)

                db.commit()
                total_results += adv_results
                logger.info(f"SEO tracking done for {adv.company_name}: {adv_results} results")

            logger.info(f"Daily SEO tracking complete: {total_results} total results for {len(advertisers)} advertisers")
        except Exception as e:
            logger.error(f"Daily SEO tracking failed: {e}")
        finally:
            db.close()

    async def daily_geo_tracking(self):
        """Run GEO (AI engine) tracking for ALL active advertisers automatically."""
        logger.info(f"Starting daily GEO tracking at {datetime.utcnow()}")

        db = SessionLocal()
        try:
            from database import Advertiser, AdvertiserCompetitor, GeoResult
            from services.geo_analyzer import geo_analyzer, get_geo_queries
            from core.sectors import get_sector_label

            advertisers = db.query(Advertiser).filter(Advertiser.is_active == True).all()
            total_mentions = 0

            for adv in advertisers:
                competitors = (
                    db.query(Competitor)
                    .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
                    .filter(AdvertiserCompetitor.advertiser_id == adv.id, Competitor.is_active == True)
                    .all()
                )
                if not competitors:
                    continue

                sector = adv.sector or "supermarche"
                sector_label = get_sector_label(sector)
                comp_map = {c.name.lower(): c for c in competitors}
                brand_names = [c.name for c in competitors]

                logger.info(f"GEO tracking: {adv.company_name} ({sector}) — {len(competitors)} competitors")

                try:
                    results, errors = await geo_analyzer.run_full_analysis(brand_names, sector=sector, sector_label=sector_label)
                except Exception as e:
                    logger.error(f"GEO tracking failed for {adv.company_name}: {e}")
                    continue

                now = datetime.utcnow()
                adv_mentions = 0

                for r in results:
                    name_lower = r["brand_name"].lower()
                    comp = comp_map.get(name_lower)
                    if not comp:
                        for cname, c in comp_map.items():
                            if name_lower in cname or cname in name_lower:
                                comp = c
                                break

                    geo = GeoResult(
                        user_id=None,
                        advertiser_id=adv.id,
                        keyword=r["keyword"],
                        query=r["query"],
                        platform=r["platform"],
                        raw_answer=r["raw_answer"],
                        analysis=r["analysis"],
                        competitor_id=comp.id if comp else None,
                        mentioned=True,
                        position_in_answer=r["position_in_answer"],
                        recommended=r["recommended"],
                        sentiment=r["sentiment"],
                        context_snippet=r["context_snippet"],
                        primary_recommendation=r["primary_recommendation"],
                        recorded_at=now,
                    )
                    db.add(geo)
                    adv_mentions += 1

                db.commit()
                total_mentions += adv_mentions
                logger.info(f"GEO tracking done for {adv.company_name}: {adv_mentions} mentions")

            logger.info(f"Daily GEO tracking complete: {total_mentions} total mentions for {len(advertisers)} advertisers")
        except Exception as e:
            logger.error(f"Daily GEO tracking failed: {e}")
        finally:
            db.close()

    async def daily_google_trends(self):
        """Collect Google Trends interest data for ALL active advertisers."""
        import asyncio
        logger.info(f"Starting daily Google Trends collection at {datetime.utcnow()}")

        db = SessionLocal()
        try:
            from database import Advertiser, AdvertiserCompetitor
            from services.searchapi import searchapi

            advertisers = db.query(Advertiser).filter(Advertiser.is_active == True).all()
            total_points = 0

            for adv in advertisers:
                competitors = (
                    db.query(Competitor)
                    .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
                    .filter(AdvertiserCompetitor.advertiser_id == adv.id, Competitor.is_active == True)
                    .all()
                )
                if not competitors:
                    continue

                keywords = [c.name for c in competitors]
                kw_to_comp = {c.name: c.id for c in competitors}

                logger.info(f"Google Trends: {adv.company_name} — {len(keywords)} keywords")

                try:
                    result = await searchapi.fetch_google_trends(keywords, geo="FR")

                    if result.get("success") and result.get("timeline_data"):
                        adv_points = 0
                        for point in result["timeline_data"]:
                            date_str = point.get("date", "")
                            for kw, val in point.get("values", {}).items():
                                comp_id = kw_to_comp.get(kw)
                                if comp_id is not None:
                                    db.add(GoogleTrendsData(
                                        competitor_id=comp_id,
                                        keyword=kw,
                                        date=date_str,
                                        value=val,
                                    ))
                                    adv_points += 1

                        db.commit()
                        total_points += adv_points
                        logger.info(f"Google Trends done for {adv.company_name}: {adv_points} data points")
                    else:
                        logger.warning(f"Google Trends: no data for {adv.company_name}: {result.get('error', 'empty')}")

                except Exception as e:
                    logger.error(f"Google Trends error for {adv.company_name}: {e}")
                    db.rollback()

                await asyncio.sleep(1)

            logger.info(f"Daily Google Trends complete: {total_points} total data points for {len(advertisers)} advertisers")
        except Exception as e:
            logger.error(f"Daily Google Trends failed: {e}")
        finally:
            db.close()

    async def daily_google_news(self):
        """Collect Google News articles for ALL active advertisers."""
        import asyncio
        logger.info(f"Starting daily Google News collection at {datetime.utcnow()}")

        db = SessionLocal()
        try:
            from database import Advertiser, AdvertiserCompetitor
            from services.searchapi import searchapi
            from sqlalchemy.exc import IntegrityError

            advertisers = db.query(Advertiser).filter(Advertiser.is_active == True).all()
            total_added = 0

            for adv in advertisers:
                competitors = (
                    db.query(Competitor)
                    .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
                    .filter(AdvertiserCompetitor.advertiser_id == adv.id, Competitor.is_active == True)
                    .all()
                )
                if not competitors:
                    continue

                logger.info(f"Google News: {adv.company_name} — {len(competitors)} competitors")
                adv_added = 0

                for comp in competitors:
                    try:
                        result = await searchapi.fetch_google_news(comp.name)
                        if not result.get("success"):
                            logger.warning(f"Google News fetch failed for {comp.name}: {result.get('error')}")
                            continue

                        for article in result.get("articles", []):
                            if not article.get("link"):
                                continue
                            news = GoogleNewsArticle(
                                competitor_id=comp.id,
                                title=article.get("title", ""),
                                link=article["link"],
                                source=article.get("source", ""),
                                date=article.get("date", ""),
                                snippet=article.get("snippet", ""),
                                thumbnail=article.get("thumbnail", ""),
                            )
                            db.add(news)
                            try:
                                db.flush()
                                adv_added += 1
                            except IntegrityError:
                                db.rollback()

                    except Exception as e:
                        logger.error(f"Google News error for {comp.name}: {e}")

                    await asyncio.sleep(0.5)

                try:
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.error(f"Google News commit error for {adv.company_name}: {e}")

                total_added += adv_added
                logger.info(f"Google News done for {adv.company_name}: {adv_added} new articles")

            logger.info(f"Daily Google News complete: {total_added} total new articles for {len(advertisers)} advertisers")
        except Exception as e:
            logger.error(f"Daily Google News failed: {e}")
        finally:
            db.close()

    async def daily_vgeo_analysis(self):
        """Run VGEO (Video GEO) analysis for ALL active advertisers automatically."""
        logger.info(f"Starting daily VGEO analysis at {datetime.utcnow()}")

        db = SessionLocal()
        try:
            from database import Advertiser, AdvertiserCompetitor, VgeoReport
            from services.vgeo_analyzer import vgeo_analyzer

            advertisers = db.query(Advertiser).filter(Advertiser.is_active == True).all()
            total_reports = 0

            for adv in advertisers:
                # Verify advertiser has competitors
                has_competitors = (
                    db.query(Competitor)
                    .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
                    .filter(AdvertiserCompetitor.advertiser_id == adv.id, Competitor.is_active == True)
                    .first()
                )
                if not has_competitors:
                    continue

                logger.info(f"VGEO analysis: {adv.company_name}")

                try:
                    result = await vgeo_analyzer.analyze(adv.id, db)

                    report = VgeoReport(
                        advertiser_id=adv.id,
                        score_total=result["score"]["total"],
                        score_alignment=result["score"]["alignment"],
                        score_freshness=result["score"]["freshness"],
                        score_presence=result["score"]["presence"],
                        score_competitivity=result["score"]["competitivity"],
                        report_data=result,
                    )
                    db.add(report)
                    db.commit()
                    total_reports += 1
                    logger.info(f"VGEO analysis done for {adv.company_name}: score {result['score']['total']}/100")
                except Exception as e:
                    logger.error(f"VGEO analysis failed for {adv.company_name}: {e}")
                    db.rollback()

            logger.info(f"Daily VGEO analysis complete: {total_reports} reports for {len(advertisers)} advertisers")
        except Exception as e:
            logger.error(f"Daily VGEO analysis failed: {e}")
        finally:
            db.close()

    async def daily_aso_analysis(self):
        """Run ASO scoring for ALL active advertisers' competitors with app store IDs."""
        import asyncio
        import json
        import math

        logger.info(f"Starting daily ASO analysis at {datetime.utcnow()}")

        db = SessionLocal()
        try:
            from database import Advertiser, AdvertiserCompetitor
            from sqlalchemy import desc
            from routers.aso import (
                WEIGHTS,
                _enrich_playstore,
                _enrich_appstore,
                _compute_metadata_score,
                _compute_visual_score,
                _compute_rating_score,
                _compute_reviews_score,
                _compute_freshness_score,
            )

            advertisers = db.query(Advertiser).filter(Advertiser.is_active == True).all()
            total_scored = 0

            for adv in advertisers:
                competitors = (
                    db.query(Competitor)
                    .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
                    .filter(AdvertiserCompetitor.advertiser_id == adv.id, Competitor.is_active == True)
                    .all()
                )

                # Filter to only competitors with app store IDs
                app_competitors = [
                    c for c in competitors
                    if c.playstore_app_id or c.appstore_app_id
                ]
                if not app_competitors:
                    continue

                logger.info(f"ASO analysis: {adv.company_name} — {len(app_competitors)} competitors with app IDs")

                # First pass: get latest DB data and max reviews for normalization
                max_reviews_ps = 1
                max_reviews_as = 1
                competitor_db_data = {}

                for comp in app_competitors:
                    ps_latest = None
                    as_latest = None
                    if comp.playstore_app_id:
                        ps_latest = (
                            db.query(AppData)
                            .filter(AppData.competitor_id == comp.id, AppData.store == "playstore")
                            .order_by(desc(AppData.recorded_at))
                            .first()
                        )
                        if ps_latest and ps_latest.reviews_count:
                            max_reviews_ps = max(max_reviews_ps, ps_latest.reviews_count)
                    if comp.appstore_app_id:
                        as_latest = (
                            db.query(AppData)
                            .filter(AppData.competitor_id == comp.id, AppData.store == "appstore")
                            .order_by(desc(AppData.recorded_at))
                            .first()
                        )
                        if as_latest and as_latest.reviews_count:
                            max_reviews_as = max(max_reviews_as, as_latest.reviews_count)
                    competitor_db_data[comp.id] = (ps_latest, as_latest)

                # Live enrichment (parallel)
                loop = asyncio.get_event_loop()

                async def enrich_competitor(comp):
                    ps_extra = {}
                    as_extra = {}
                    tasks = []
                    if comp.playstore_app_id:
                        tasks.append(("ps", loop.run_in_executor(None, _enrich_playstore, comp.playstore_app_id)))
                    if comp.appstore_app_id:
                        tasks.append(("as", _enrich_appstore(comp.appstore_app_id)))

                    for label, task in tasks:
                        try:
                            result = await asyncio.wait_for(task, timeout=15)
                            if label == "ps":
                                ps_extra = result
                            else:
                                as_extra = result
                        except (asyncio.TimeoutError, Exception) as e:
                            logger.warning(f"ASO enrichment timeout for {comp.name} ({label}): {e}")

                    return comp.id, ps_extra, as_extra

                enrichment_tasks = [enrich_competitor(comp) for comp in app_competitors]
                enrichment_results = await asyncio.gather(*enrichment_tasks, return_exceptions=True)

                enrichment_map = {}
                for r in enrichment_results:
                    if isinstance(r, tuple):
                        enrichment_map[r[0]] = (r[1], r[2])

                # Second pass: compute and cache scores
                competitor_scores = []
                for comp in app_competitors:
                    ps_latest, as_latest = competitor_db_data.get(comp.id, (None, None))
                    ps_extra, as_extra = enrichment_map.get(comp.id, ({}, {}))

                    entry = {
                        "competitor_id": comp.id,
                        "competitor_name": comp.name,
                    }
                    scores_list = []

                    # Play Store ASO
                    if ps_latest:
                        metadata = _compute_metadata_score(
                            title=ps_latest.app_name or "",
                            description=ps_latest.description or "",
                            changelog=ps_latest.changelog,
                            short_desc=ps_extra.get("short_description", ""),
                            store="playstore",
                        )
                        visual = _compute_visual_score(
                            screenshot_urls=ps_extra.get("screenshot_urls", []),
                            video_url=ps_extra.get("video_url"),
                            header_image=ps_extra.get("header_image"),
                            icon_url=ps_extra.get("icon_url"),
                            store="playstore",
                        )
                        rating = _compute_rating_score(ps_latest.rating, ps_extra.get("histogram"))
                        reviews = _compute_reviews_score(ps_latest.reviews_count, max_reviews_ps)
                        freshness = _compute_freshness_score(ps_latest.last_updated)

                        ps_total = (
                            metadata["total"] * WEIGHTS["metadata"]
                            + visual["total"] * WEIGHTS["visual"]
                            + rating["total"] * WEIGHTS["rating"]
                            + reviews["total"] * WEIGHTS["reviews"]
                            + freshness["total"] * WEIGHTS["freshness"]
                        )

                        entry["playstore"] = {
                            "aso_score": round(ps_total, 1),
                            "metadata_score": metadata["total"],
                            "visual_score": visual["total"],
                            "rating_score": rating["total"],
                            "reviews_score": reviews["total"],
                            "freshness_score": freshness["total"],
                            "rating": ps_latest.rating,
                            "reviews_count": ps_latest.reviews_count,
                        }
                        scores_list.append(ps_total)

                    # App Store ASO
                    if as_latest:
                        metadata = _compute_metadata_score(
                            title=as_latest.app_name or "",
                            description=as_latest.description or "",
                            changelog=as_latest.changelog,
                            store="appstore",
                        )
                        visual = _compute_visual_score(
                            screenshot_urls=as_extra.get("screenshot_urls", []),
                            video_url=None,
                            icon_url=as_extra.get("icon_url"),
                            store="appstore",
                        )
                        rating = _compute_rating_score(as_latest.rating)
                        reviews = _compute_reviews_score(as_latest.reviews_count, max_reviews_as)
                        freshness = _compute_freshness_score(as_latest.last_updated)

                        as_total = (
                            metadata["total"] * WEIGHTS["metadata"]
                            + visual["total"] * WEIGHTS["visual"]
                            + rating["total"] * WEIGHTS["rating"]
                            + reviews["total"] * WEIGHTS["reviews"]
                            + freshness["total"] * WEIGHTS["freshness"]
                        )

                        entry["appstore"] = {
                            "aso_score": round(as_total, 1),
                            "metadata_score": metadata["total"],
                            "visual_score": visual["total"],
                            "rating_score": rating["total"],
                            "reviews_score": reviews["total"],
                            "freshness_score": freshness["total"],
                            "rating": as_latest.rating,
                            "reviews_count": as_latest.reviews_count,
                        }
                        scores_list.append(as_total)

                    entry["aso_score_avg"] = round(sum(scores_list) / len(scores_list), 1) if scores_list else 0
                    competitor_scores.append(entry)
                    total_scored += 1

                # Sort and log results
                competitor_scores.sort(key=lambda x: x["aso_score_avg"], reverse=True)
                if competitor_scores:
                    logger.info(
                        f"ASO analysis done for {adv.company_name}: "
                        f"{len(competitor_scores)} competitors scored, "
                        f"top={competitor_scores[0]['competitor_name']}({competitor_scores[0]['aso_score_avg']})"
                    )

            logger.info(f"Daily ASO analysis complete: {total_scored} total competitors scored for {len(advertisers)} advertisers")
        except Exception as e:
            logger.error(f"Daily ASO analysis failed: {e}")
        finally:
            db.close()

    async def weekly_market_data_refresh(self):
        """Refresh market data from data.gouv.fr."""
        logger.info(f"Starting weekly market data refresh at {datetime.utcnow()}")
        try:
            from services.datagouv import datagouv_service
            await datagouv_service.refresh_all()
            logger.info("Weekly market data refresh completed")
        except Exception as e:
            logger.error(f"Weekly market refresh failed: {e}")

    async def monthly_meta_token_refresh(self):
        """Refresh the Meta Ad Library long-lived token before it expires."""
        logger.info(f"Starting monthly Meta token refresh at {datetime.utcnow()}")
        try:
            from services.meta_ad_library import meta_ad_library
            result = await meta_ad_library.refresh_long_lived_token()
            if result["success"]:
                logger.info(
                    f"Meta token refresh succeeded. "
                    f"New token expires in {result.get('expires_days', '?')} days"
                )
            else:
                logger.error(f"Meta token refresh failed: {result.get('error')}")
        except Exception as e:
            logger.error(f"Meta token refresh job failed: {e}")

    def get_status(self) -> dict:
        """Get scheduler status and next run times."""
        jobs = [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            }
            for job in self.scheduler.get_jobs()
        ]

        return {
            "enabled": settings.SCHEDULER_ENABLED,
            "running": self.scheduler.running,
            "jobs": jobs
        }


# Singleton instance
scheduler = DataCollectionScheduler()

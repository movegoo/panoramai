"""
Scheduler service for automated data collection.
Uses APScheduler for daily background jobs.
"""
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from database import SessionLocal, Competitor, AppData, InstagramData, TikTokData, YouTubeData, Ad, SnapchatData
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

        # Weekly market data refresh (Sundays 3 AM)
        self.scheduler.add_job(
            self.weekly_market_data_refresh,
            CronTrigger(day_of_week="sun", hour=3, minute=0),
            id="weekly_market_refresh",
            name="Weekly Market Data Refresh",
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
        """Fetch Facebook/Instagram ads from Ad Library."""
        try:
            from services.scrapecreators import scrapecreators
            from routers.facebook import _name_matches, _parse_date
            import json

            # Prefer page_id-based fetch with pagination
            page_id = competitor.facebook_page_id
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

            from database import Ad
            new_count = 0
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
                logger.info(f"Ads: {new_count} new ads stored for {name}")
        except Exception as e:
            logger.error(f"Ads fetch failed for {name}: {e}")

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
                        has_image = ad.creative_url and not any(
                            p in (ad.creative_url or "") for p in SKIP_URL_PATTERNS
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

    async def weekly_market_data_refresh(self):
        """Refresh market data from data.gouv.fr."""
        logger.info(f"Starting weekly market data refresh at {datetime.utcnow()}")
        try:
            from services.datagouv import datagouv_service
            await datagouv_service.refresh_all()
            logger.info("Weekly market data refresh completed")
        except Exception as e:
            logger.error(f"Weekly market refresh failed: {e}")

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

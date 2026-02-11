"""
Scheduler service for automated data collection.
Uses APScheduler for daily background jobs.
"""
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from database import SessionLocal, Competitor, AppData, InstagramData, TikTokData, YouTubeData
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
        except Exception as e:
            logger.error(f"Error in daily data collection: {e}")
        finally:
            db.close()

    async def _fetch_competitor_data(self, db: Session, competitor: Competitor):
        """Fetch all data sources for a single competitor."""
        name = competitor.name

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
        """Fetch Instagram data via ScrapeCreators."""
        try:
            from services.scrapecreators import scrapecreators

            result = await scrapecreators.fetch_instagram_profile(competitor.instagram_username)
            if result.get("success"):
                ig_data = InstagramData(
                    competitor_id=competitor.id,
                    followers=result.get("followers", 0),
                    following=result.get("following", 0),
                    posts_count=result.get("posts_count", 0),
                    avg_likes=result.get("avg_likes", 0),
                    avg_comments=result.get("avg_comments", 0),
                    engagement_rate=result.get("engagement_rate", 0),
                    bio=result.get("bio")
                )
                db.add(ig_data)
                db.commit()
                logger.info(f"Instagram data fetched for {name}")
            else:
                logger.warning(f"Instagram fetch returned no data for {name}: {result.get('error')}")
        except Exception as e:
            logger.error(f"Instagram fetch failed for {name}: {e}")

    async def _fetch_tiktok(self, db: Session, competitor: Competitor, name: str):
        """Fetch TikTok data."""
        try:
            from services.tiktok_scraper import tiktok_scraper

            result = await tiktok_scraper.fetch_profile(competitor.tiktok_username)
            if result.get("success"):
                tt_data = TikTokData(
                    competitor_id=competitor.id,
                    username=competitor.tiktok_username,
                    followers=result.get("followers", 0),
                    following=result.get("following", 0),
                    likes=result.get("likes", 0),
                    videos_count=result.get("videos_count", 0),
                    bio=result.get("bio"),
                    verified=result.get("verified", False)
                )
                db.add(tt_data)
                db.commit()
                logger.info(f"TikTok data fetched for {name}")
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

    async def weekly_market_data_refresh(self):
        """Refresh market data from data.gouv.fr."""
        logger.info(f"Starting weekly market data refresh at {datetime.utcnow()}")
        try:
            from services.datagouv import datagouv_service
            await datagouv_service.refresh_all_datasets()
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

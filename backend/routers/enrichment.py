"""
Global enrichment router.
Triggers all platform fetches for all competitors in parallel.
"""
import asyncio
import traceback
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import (
    get_db, User, Competitor, InstagramData, TikTokData,
    YouTubeData, AppData, Ad,
)
from core.auth import get_current_user
from core.permissions import get_user_competitors, parse_advertiser_header
from services.scrapecreators import scrapecreators

router = APIRouter()


async def _fetch_instagram(competitor: Competitor, db: Session) -> dict:
    """Fetch Instagram profile data."""
    if not competitor.instagram_username:
        return {"platform": "instagram", "competitor": competitor.name, "status": "skipped", "reason": "no username"}
    try:
        data = await scrapecreators.fetch_instagram_profile(competitor.instagram_username)
        if not data:
            return {"platform": "instagram", "competitor": competitor.name, "status": "error", "reason": "no data returned"}
        record = InstagramData(
            competitor_id=competitor.id,
            followers=data.get("followers") or data.get("follower_count"),
            following=data.get("following") or data.get("following_count"),
            posts_count=data.get("media_count") or data.get("posts_count"),
            avg_likes=data.get("avg_likes"),
            avg_comments=data.get("avg_comments"),
            engagement_rate=data.get("engagement_rate"),
            bio=data.get("biography") or data.get("bio"),
        )
        db.add(record)
        db.commit()
        return {"platform": "instagram", "competitor": competitor.name, "status": "ok", "followers": record.followers}
    except Exception as e:
        return {"platform": "instagram", "competitor": competitor.name, "status": "error", "reason": str(e)}


async def _fetch_tiktok(competitor: Competitor, db: Session) -> dict:
    """Fetch TikTok profile data."""
    if not competitor.tiktok_username:
        return {"platform": "tiktok", "competitor": competitor.name, "status": "skipped", "reason": "no username"}
    try:
        data = await scrapecreators.fetch_tiktok_profile(competitor.tiktok_username)
        if not data:
            return {"platform": "tiktok", "competitor": competitor.name, "status": "error", "reason": "no data returned"}
        record = TikTokData(
            competitor_id=competitor.id,
            username=competitor.tiktok_username,
            followers=data.get("followers") or data.get("follower_count"),
            following=data.get("following") or data.get("following_count"),
            likes=data.get("likes") or data.get("heart_count") or data.get("total_likes"),
            videos_count=data.get("videos") or data.get("video_count"),
            bio=data.get("biography") or data.get("bio") or data.get("signature"),
            verified=data.get("verified", False),
        )
        db.add(record)
        db.commit()
        return {"platform": "tiktok", "competitor": competitor.name, "status": "ok", "followers": record.followers}
    except Exception as e:
        return {"platform": "tiktok", "competitor": competitor.name, "status": "error", "reason": str(e)}


async def _fetch_youtube(competitor: Competitor, db: Session) -> dict:
    """Fetch YouTube channel data."""
    if not competitor.youtube_channel_id:
        return {"platform": "youtube", "competitor": competitor.name, "status": "skipped", "reason": "no channel_id"}
    try:
        yt_id = competitor.youtube_channel_id
        if yt_id.startswith("UC"):
            data = await scrapecreators.fetch_youtube_channel(channel_id=yt_id)
        else:
            # Handle formats like "user/ikeafrance" or just "ikeafrance"
            handle = yt_id.split("/")[-1] if "/" in yt_id else yt_id
            data = await scrapecreators.fetch_youtube_channel(handle=handle)
        if not data:
            return {"platform": "youtube", "competitor": competitor.name, "status": "error", "reason": "no data returned"}
        record = YouTubeData(
            competitor_id=competitor.id,
            channel_id=competitor.youtube_channel_id,
            channel_name=data.get("channel_name") or data.get("title"),
            subscribers=data.get("subscribers") or data.get("subscriber_count"),
            total_views=data.get("total_views") or data.get("view_count"),
            videos_count=data.get("videos") or data.get("video_count"),
            avg_views=data.get("avg_views"),
            avg_likes=data.get("avg_likes"),
            avg_comments=data.get("avg_comments"),
            engagement_rate=data.get("engagement_rate"),
        )
        db.add(record)
        db.commit()
        return {"platform": "youtube", "competitor": competitor.name, "status": "ok", "subscribers": record.subscribers}
    except Exception as e:
        return {"platform": "youtube", "competitor": competitor.name, "status": "error", "reason": str(e)}


async def _fetch_playstore(competitor: Competitor, db: Session) -> dict:
    """Fetch Play Store app data."""
    if not competitor.playstore_app_id:
        return {"platform": "playstore", "competitor": competitor.name, "status": "skipped", "reason": "no app_id"}
    try:
        from google_play_scraper import app as gplay_app
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: gplay_app(competitor.playstore_app_id, lang="fr", country="fr"))
        if not data:
            return {"platform": "playstore", "competitor": competitor.name, "status": "error", "reason": "no data returned"}
        record = AppData(
            competitor_id=competitor.id,
            store_type="playstore",
            app_id=competitor.playstore_app_id,
            app_name=data.get("title"),
            rating=data.get("score"),
            reviews_count=data.get("ratings"),
            downloads=data.get("installs") or data.get("realInstalls"),
            version=data.get("version"),
            last_updated=data.get("lastUpdatedOn") or data.get("updated"),
            description=data.get("description", "")[:2000] if data.get("description") else None,
            changelog=data.get("recentChanges", "")[:1000] if data.get("recentChanges") else None,
        )
        db.add(record)
        db.commit()
        return {"platform": "playstore", "competitor": competitor.name, "status": "ok", "rating": record.rating, "downloads": str(record.downloads)}
    except Exception as e:
        return {"platform": "playstore", "competitor": competitor.name, "status": "error", "reason": str(e)}


async def _fetch_appstore(competitor: Competitor, db: Session) -> dict:
    """Fetch App Store data via iTunes Lookup API."""
    if not competitor.appstore_app_id:
        return {"platform": "appstore", "competitor": competitor.name, "status": "skipped", "reason": "no app_id"}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"https://itunes.apple.com/lookup?id={competitor.appstore_app_id}&country=fr")
            results = resp.json().get("results", [])
        if not results:
            return {"platform": "appstore", "competitor": competitor.name, "status": "error", "reason": "not found in iTunes"}
        app_info = results[0]
        record = AppData(
            competitor_id=competitor.id,
            store_type="appstore",
            app_id=competitor.appstore_app_id,
            app_name=app_info.get("trackName"),
            rating=app_info.get("averageUserRating"),
            reviews_count=app_info.get("userRatingCount"),
            version=app_info.get("version"),
            last_updated=app_info.get("currentVersionReleaseDate"),
            description=app_info.get("description", "")[:2000] if app_info.get("description") else None,
            changelog=app_info.get("releaseNotes", "")[:1000] if app_info.get("releaseNotes") else None,
        )
        db.add(record)
        db.commit()
        return {"platform": "appstore", "competitor": competitor.name, "status": "ok", "rating": record.rating}
    except Exception as e:
        return {"platform": "appstore", "competitor": competitor.name, "status": "error", "reason": str(e)}


async def _fetch_facebook_ads(competitor: Competitor, db: Session) -> dict:
    """Fetch Meta ads from Ad Library."""
    search_term = competitor.name
    if not search_term:
        return {"platform": "facebook_ads", "competitor": competitor.name, "status": "skipped", "reason": "no name"}
    try:
        ads = await scrapecreators.search_facebook_ads(search_term, country="FR", limit=25)
        if not ads:
            return {"platform": "facebook_ads", "competitor": competitor.name, "status": "ok", "new_ads": 0}
        new_count = 0
        for ad_data in ads:
            ad_id = ad_data.get("adArchiveID") or ad_data.get("ad_archive_id") or ad_data.get("id")
            if not ad_id:
                continue
            existing = db.query(Ad).filter(Ad.platform_ad_id == str(ad_id)).first()
            if existing:
                continue
            ad = Ad(
                competitor_id=competitor.id,
                platform="meta",
                platform_ad_id=str(ad_id),
                title=ad_data.get("title") or ad_data.get("ad_creative_bodies", [None])[0] if isinstance(ad_data.get("ad_creative_bodies"), list) else ad_data.get("ad_creative_bodies"),
                body=ad_data.get("body") or ad_data.get("ad_creative_bodies", [None])[0] if isinstance(ad_data.get("ad_creative_bodies"), list) else None,
                image_url=ad_data.get("snapshot", {}).get("images", [{}])[0].get("url") if isinstance(ad_data.get("snapshot", {}).get("images"), list) and ad_data.get("snapshot", {}).get("images") else ad_data.get("image_url"),
                landing_url=ad_data.get("ad_creative_link_captions", [None])[0] if isinstance(ad_data.get("ad_creative_link_captions"), list) else ad_data.get("landing_page_url"),
                is_active=ad_data.get("isActive") or ad_data.get("is_active", True),
                started_at=ad_data.get("startDate") or ad_data.get("ad_delivery_start_time"),
                raw_data=ad_data,
            )
            db.add(ad)
            new_count += 1
        db.commit()
        return {"platform": "facebook_ads", "competitor": competitor.name, "status": "ok", "total_fetched": len(ads), "new_ads": new_count}
    except Exception as e:
        return {"platform": "facebook_ads", "competitor": competitor.name, "status": "error", "reason": str(e)}


@router.post("/all")
async def enrich_all(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Run all enrichments for all competitors in parallel.
    Platforms: Instagram, TikTok, YouTube, Play Store, App Store, Facebook Ads.
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)

    if not competitors:
        raise HTTPException(status_code=404, detail="Aucun concurrent trouvé")

    # Build all tasks
    tasks = []
    for comp in competitors:
        tasks.append(_fetch_instagram(comp, db))
        tasks.append(_fetch_tiktok(comp, db))
        tasks.append(_fetch_youtube(comp, db))
        tasks.append(_fetch_playstore(comp, db))
        tasks.append(_fetch_appstore(comp, db))
        tasks.append(_fetch_facebook_ads(comp, db))

    # Run all with timeout
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    output = []
    for r in results:
        if isinstance(r, Exception):
            output.append({"status": "error", "reason": str(r)})
        else:
            output.append(r)

    # Summary
    ok_count = sum(1 for r in output if isinstance(r, dict) and r.get("status") == "ok")
    skip_count = sum(1 for r in output if isinstance(r, dict) and r.get("status") == "skipped")
    err_count = sum(1 for r in output if isinstance(r, dict) and r.get("status") == "error")

    return {
        "message": f"Enrichissement terminé: {ok_count} OK, {skip_count} ignorés, {err_count} erreurs",
        "competitors_count": len(competitors),
        "total_tasks": len(tasks),
        "ok": ok_count,
        "skipped": skip_count,
        "errors": err_count,
        "details": output,
    }

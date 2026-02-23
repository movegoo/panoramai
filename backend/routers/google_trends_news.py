"""
Google Trends & Google News — Search interest tracking and press monitoring.
Uses SearchAPI.io (same key as Meta Ad Library enrichment).
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import (
    get_db, Competitor, User,
    GoogleTrendsData, GoogleNewsArticle,
)
from services.searchapi import searchapi
from core.auth import get_current_user
from core.permissions import (
    get_user_competitors, get_user_competitor_ids,
    parse_advertiser_header, verify_competitor_ownership,
)

logger = logging.getLogger(__name__)
router = APIRouter()

CACHE_HOURS = 24  # Re-fetch trends data after this many hours


@router.get("/trends/interest")
async def get_trends_interest(
    geo: str = Query("FR", description="Country code"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Compare Google Trends search interest for all competitors.
    Returns timeseries data (date + value 0-100 per competitor).
    Caches results for 24h.
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)
    if not competitors:
        return {"competitors": {}, "source": "empty"}

    # Check if we have recent data (< CACHE_HOURS)
    cutoff = datetime.utcnow() - timedelta(hours=CACHE_HOURS)
    recent = (
        db.query(GoogleTrendsData)
        .filter(
            GoogleTrendsData.competitor_id.in_([c.id for c in competitors]),
            GoogleTrendsData.recorded_at >= cutoff,
        )
        .first()
    )

    if not recent:
        # Fetch fresh data from SearchAPI
        keywords = [c.name for c in competitors]
        result = await searchapi.fetch_google_trends(keywords, geo=geo)

        if result.get("success") and result.get("timeline_data"):
            # Map keyword -> competitor_id
            kw_to_comp = {}
            for c in competitors:
                kw_to_comp[c.name] = c.id

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
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(f"Failed to store trends data: {e}")

    # Return data from DB
    comp_ids = [c.id for c in competitors]
    rows = (
        db.query(GoogleTrendsData)
        .filter(GoogleTrendsData.competitor_id.in_(comp_ids))
        .order_by(GoogleTrendsData.date)
        .all()
    )

    comp_name_map = {c.id: c.name for c in competitors}
    result_data: dict[int, list] = {c.id: [] for c in competitors}
    for r in rows:
        result_data[r.competitor_id].append({
            "date": r.date,
            "value": r.value,
        })

    return {
        "competitors": {
            str(cid): {
                "name": comp_name_map[cid],
                "data": result_data[cid],
            }
            for cid in comp_ids
        },
        "source": "cache" if recent else "fresh",
    }


@router.get("/trends/related/{competitor_id}")
async def get_trends_related(
    competitor_id: int,
    geo: str = Query("FR"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Get rising + top related queries for a specific competitor.
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp = verify_competitor_ownership(db, competitor_id, user, advertiser_id=adv_id)

    result = await searchapi.fetch_google_trends_related(comp.name, geo=geo)
    if not result.get("success"):
        return {"rising": [], "top": [], "error": result.get("error")}

    return {
        "competitor_id": competitor_id,
        "name": comp.name,
        "rising": result.get("rising", []),
        "top": result.get("top", []),
    }


@router.get("/news")
async def get_news(
    competitor_id: Optional[int] = Query(None, description="Filter by competitor"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Get collected news articles for competitors.
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp_ids = get_user_competitor_ids(db, user, advertiser_id=adv_id)
    if not comp_ids:
        return {"articles": [], "total": 0}

    query = db.query(GoogleNewsArticle).filter(
        GoogleNewsArticle.competitor_id.in_(comp_ids)
    )
    if competitor_id and competitor_id in comp_ids:
        query = query.filter(GoogleNewsArticle.competitor_id == competitor_id)

    total = query.count()
    articles = query.order_by(GoogleNewsArticle.collected_at.desc()).limit(limit).all()

    # Get competitor names
    comps = {c.id: c.name for c in db.query(Competitor).filter(Competitor.id.in_(comp_ids)).all()}

    return {
        "articles": [
            {
                "id": a.id,
                "competitor_id": a.competitor_id,
                "competitor_name": comps.get(a.competitor_id, ""),
                "title": a.title,
                "link": a.link,
                "source": a.source,
                "date": a.date,
                "snippet": a.snippet,
                "thumbnail": a.thumbnail,
                "collected_at": a.collected_at.isoformat() if a.collected_at else None,
            }
            for a in articles
        ],
        "total": total,
    }


@router.post("/news/refresh")
async def refresh_news(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Force-collect fresh news for all competitors.
    Deduplicates by link (unique constraint).
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)
    if not competitors:
        return {"added": 0, "competitors": 0}

    total_added = 0
    for comp in competitors:
        result = await searchapi.fetch_google_news(comp.name)
        if not result.get("success"):
            logger.warning(f"News fetch failed for {comp.name}: {result.get('error')}")
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
                total_added += 1
            except IntegrityError:
                db.rollback()

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"News refresh commit error: {e}")

    return {
        "added": total_added,
        "competitors": len(competitors),
    }


@router.get("/news/latest")
async def get_latest_news(
    limit: int = Query(5, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Get the N most recent news articles (dashboard widget).
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp_ids = get_user_competitor_ids(db, user, advertiser_id=adv_id)
    if not comp_ids:
        return {"articles": []}

    articles = (
        db.query(GoogleNewsArticle)
        .filter(GoogleNewsArticle.competitor_id.in_(comp_ids))
        .order_by(GoogleNewsArticle.collected_at.desc())
        .limit(limit)
        .all()
    )

    comps = {c.id: c.name for c in db.query(Competitor).filter(Competitor.id.in_(comp_ids)).all()}

    return {
        "articles": [
            {
                "id": a.id,
                "competitor_id": a.competitor_id,
                "competitor_name": comps.get(a.competitor_id, ""),
                "title": a.title,
                "link": a.link,
                "source": a.source,
                "date": a.date,
                "snippet": a.snippet,
                "thumbnail": a.thumbnail,
                "collected_at": a.collected_at.isoformat() if a.collected_at else None,
            }
            for a in articles
        ],
    }

"""
Meta Ads Router.
Veille publicitaire concurrentielle via ScrapeCreators Ad Library API.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime, timedelta
import json
import asyncio
import logging

from database import get_db, Competitor, Ad, User
from core.auth import get_optional_user, claim_orphans
from services.scrapecreators import scrapecreators

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/ads/all")
async def get_all_ads(
    active_only: bool = False,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Retourne TOUTES les publicités des concurrents actifs."""
    if user:
        claim_orphans(db, user)
    # Only show ads for active competitors (filtered by user if logged in)
    comp_query = db.query(Competitor).filter(Competitor.is_active == True)
    if user:
        comp_query = comp_query.filter(Competitor.user_id == user.id)
    active_comps = {c.id: c.name for c in comp_query.all()}

    query = db.query(Ad).filter(Ad.competitor_id.in_(active_comps.keys()))
    if active_only:
        query = query.filter(Ad.is_active == True)
    ads = query.order_by(desc(Ad.start_date)).all()

    result = []
    for ad in ads:
        d = _serialize_ad(ad)
        d["competitor_name"] = active_comps.get(ad.competitor_id, "Inconnu")
        result.append(d)
    return result


@router.get("/ads/{competitor_id}")
async def get_competitor_ads(
    competitor_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """
    Retourne les publicités stockées pour un concurrent.
    """
    competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    query = db.query(Ad).filter(Ad.competitor_id == competitor_id)
    if active_only:
        query = query.filter(Ad.is_active == True)
    ads = query.order_by(desc(Ad.start_date)).all()

    return [_serialize_ad(ad) for ad in ads]


def _serialize_ad(ad: Ad) -> dict:
    """Serialize an Ad to JSON-friendly dict with all enriched fields."""
    return {
        "id": ad.id,
        "competitor_id": ad.competitor_id,
        "ad_id": ad.ad_id,
        "platform": ad.platform,
        "creative_url": ad.creative_url,
        "ad_text": ad.ad_text,
        "cta": ad.cta,
        "start_date": ad.start_date.isoformat() if ad.start_date else None,
        "end_date": ad.end_date.isoformat() if ad.end_date else None,
        "is_active": ad.is_active,
        "estimated_spend_min": ad.estimated_spend_min,
        "estimated_spend_max": ad.estimated_spend_max,
        "impressions_min": ad.impressions_min,
        "impressions_max": ad.impressions_max,
        "created_at": ad.created_at.isoformat() if ad.created_at else None,
        "publisher_platforms": _parse_json(ad.publisher_platforms),
        "page_id": ad.page_id,
        "page_name": ad.page_name,
        "page_categories": _parse_json(ad.page_categories),
        "page_like_count": ad.page_like_count,
        "page_profile_uri": ad.page_profile_uri,
        "page_profile_picture_url": ad.page_profile_picture_url,
        "link_url": ad.link_url,
        "display_format": ad.display_format,
        "targeted_countries": _parse_json(ad.targeted_countries),
        "ad_categories": _parse_json(ad.ad_categories),
        "contains_ai_content": ad.contains_ai_content,
        "ad_library_url": ad.ad_library_url,
        "title": ad.title,
        "link_description": ad.link_description,
        "byline": ad.byline,
        "disclaimer_label": ad.disclaimer_label,
        "age_min": ad.age_min,
        "age_max": ad.age_max,
        "gender_audience": ad.gender_audience,
        "location_audience": _parse_json(ad.location_audience),
        "eu_total_reach": ad.eu_total_reach,
        "age_country_gender_reach": _parse_json(ad.age_country_gender_reach),
        # Creative Analysis
        "creative_concept": ad.creative_concept,
        "creative_hook": ad.creative_hook,
        "creative_tone": ad.creative_tone,
        "creative_text_overlay": ad.creative_text_overlay,
        "creative_dominant_colors": _parse_json(ad.creative_dominant_colors),
        "creative_has_product": ad.creative_has_product,
        "creative_has_face": ad.creative_has_face,
        "creative_has_logo": ad.creative_has_logo,
        "creative_layout": ad.creative_layout,
        "creative_cta_style": ad.creative_cta_style,
        "creative_score": ad.creative_score,
        "creative_tags": _parse_json(ad.creative_tags),
        "creative_summary": ad.creative_summary,
        "creative_analyzed_at": ad.creative_analyzed_at.isoformat() if ad.creative_analyzed_at else None,
    }


@router.post("/fetch/{competitor_id}")
async def fetch_competitor_ads(
    competitor_id: int,
    country: str = Query("FR", description="Pays de diffusion"),
    db: Session = Depends(get_db),
):
    """
    Récupère les publicités d'un concurrent via ScrapeCreators Ad Library.
    Recherche par nom de l'entreprise.
    """
    competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    # Search by competitor name
    result = await scrapecreators.search_facebook_ads(
        company_name=competitor.name,
        country=country,
        limit=50,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=503,
            detail=f"Ad Library API error: {result.get('error', 'Unknown')}"
        )

    ads_data = result.get("ads", [])
    new_count = 0
    updated_count = 0

    for ad in ads_data:
        ad_id = str(ad.get("ad_archive_id", ""))
        if not ad_id:
            continue

        snapshot = ad.get("snapshot", {})
        page_name_val = snapshot.get("page_name", "") or ad.get("page_name", "")

        # Only store ads from this competitor's page (fuzzy match)
        if not _name_matches(competitor.name, page_name_val):
            continue

        existing = db.query(Ad).filter(Ad.ad_id == ad_id).first()

        # Extract data from snapshot
        cards = snapshot.get("cards", [])
        first_card = cards[0] if cards else {}

        ad_text = first_card.get("body") or snapshot.get("body", {}).get("text", "") or snapshot.get("caption", "")
        cta = first_card.get("cta_text") or snapshot.get("cta_text", "")
        creative_url = first_card.get("original_image_url") or first_card.get("resized_image_url") or first_card.get("video_preview_image_url", "")

        # Parse dates
        start_date = _parse_date(ad.get("start_date_string") or ad.get("start_date"))
        end_date = _parse_date(ad.get("end_date_string") or ad.get("end_date"))
        is_active = ad.get("is_active", not bool(end_date))

        # Spend/impressions ranges
        spend = ad.get("spend", {})
        spend_min = spend.get("lower_bound", 0) if isinstance(spend, dict) else 0
        spend_max = spend.get("upper_bound", 0) if isinstance(spend, dict) else 0

        impressions = ad.get("impressions", {})
        imp_min = impressions.get("lower_bound", 0) if isinstance(impressions, dict) else 0
        imp_max = impressions.get("upper_bound", 0) if isinstance(impressions, dict) else 0

        # Platforms (array)
        pub_platforms = ad.get("publisher_platform", [])
        if not isinstance(pub_platforms, list):
            pub_platforms = [pub_platforms] if pub_platforms else []
        pub_platforms_upper = [p.upper() if isinstance(p, str) else str(p) for p in pub_platforms]

        # Determine primary platform display
        platform = "facebook"
        for p in pub_platforms_upper:
            if "INSTAGRAM" in p:
                platform = "instagram"
                break

        # Enriched fields
        page_id = snapshot.get("page_id", "") or ad.get("page_id", "")
        page_categories = snapshot.get("page_categories", []) or []
        page_like_count = snapshot.get("page_like_count")
        page_profile_uri = snapshot.get("page_profile_uri", "")
        page_profile_picture_url = snapshot.get("page_profile_picture_url", "")
        link_url = first_card.get("link_url") or snapshot.get("link_url", "")
        display_format = snapshot.get("display_format", "")
        targeted_countries = ad.get("targeted_or_reached_countries", []) or []
        ad_categories = ad.get("categories", []) or []
        contains_ai = ad.get("contains_digital_created_media", False)
        ad_library_url = ad.get("url", "")
        title_val = first_card.get("title") or snapshot.get("title", "")
        link_desc = first_card.get("link_description") or snapshot.get("link_description", "")
        byline_val = snapshot.get("byline") or None
        disclaimer_val = snapshot.get("disclaimer_label") or None

        # Common fields dict
        enriched = dict(
            platform=platform,
            creative_url=creative_url,
            ad_text=ad_text,
            cta=cta,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
            estimated_spend_min=spend_min,
            estimated_spend_max=spend_max,
            impressions_min=imp_min,
            impressions_max=imp_max,
            publisher_platforms=json.dumps(pub_platforms_upper) if pub_platforms_upper else None,
            page_id=page_id or None,
            page_name=page_name_val or None,
            page_categories=json.dumps(page_categories) if page_categories else None,
            page_like_count=page_like_count,
            page_profile_uri=page_profile_uri or None,
            page_profile_picture_url=page_profile_picture_url or None,
            link_url=link_url or None,
            display_format=display_format or None,
            targeted_countries=json.dumps(targeted_countries) if targeted_countries else None,
            ad_categories=json.dumps(ad_categories) if ad_categories else None,
            contains_ai_content=contains_ai,
            ad_library_url=ad_library_url or None,
            title=title_val or None,
            link_description=link_desc[:2000] if link_desc else None,
            byline=byline_val,
            disclaimer_label=disclaimer_val,
        )

        if existing:
            for k, v in enriched.items():
                setattr(existing, k, v)
            updated_count += 1
        else:
            new_ad = Ad(competitor_id=competitor_id, ad_id=ad_id, **enriched)
            db.add(new_ad)
            new_count += 1

    db.commit()

    return {
        "message": f"Fetched {len(ads_data)} ads for {competitor.name}",
        "total_fetched": len(ads_data),
        "new_stored": new_count,
        "updated": updated_count,
        "total_available": result.get("total_available", 0),
    }


@router.post("/enrich-transparency")
async def enrich_ads_transparency(
    db: Session = Depends(get_db),
):
    """
    Enrich all Meta ads that lack EU transparency data (age, gender, location, reach)
    by fetching individual ad details from the Ad Library.
    """
    # Only enrich Meta/Facebook ads (not TikTok/Google)
    meta_platforms = ["facebook", "instagram", "messenger", "audience_network", "meta",
                      "FACEBOOK", "INSTAGRAM", "MESSENGER", "AUDIENCE_NETWORK", "META"]
    ads_to_enrich = db.query(Ad).filter(
        Ad.eu_total_reach.is_(None),
        Ad.platform.in_(meta_platforms),
    ).all()

    if not ads_to_enrich:
        return {"message": "All Meta ads already enriched", "enriched": 0, "total_meta": 0}

    enriched_count = 0
    errors = 0

    for ad in ads_to_enrich:
        try:
            detail = await scrapecreators.get_facebook_ad_detail(ad.ad_id)

            if not detail.get("success"):
                # Mark as processed (reach=0) to avoid re-processing
                ad.eu_total_reach = 0
                errors += 1
                continue

            ad.age_min = detail.get("age_min")
            ad.age_max = detail.get("age_max")
            ad.gender_audience = detail.get("gender_audience")
            # Default to 0 if null so we don't re-process
            ad.eu_total_reach = detail.get("eu_total_reach") or 0

            loc = detail.get("location_audience", [])
            if loc:
                ad.location_audience = json.dumps(loc)

            breakdown = detail.get("age_country_gender_reach_breakdown", [])
            if breakdown:
                ad.age_country_gender_reach = json.dumps(breakdown)

            enriched_count += 1

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"Error enriching ad {ad.ad_id}: {e}")
            ad.eu_total_reach = 0  # Mark as processed
            errors += 1

    db.commit()

    return {
        "message": f"Enriched {enriched_count} ads with EU transparency data",
        "enriched": enriched_count,
        "errors": errors,
        "total_meta_ads": len(ads_to_enrich),
        "remaining": len(ads_to_enrich) - enriched_count - errors,
    }


@router.get("/stats/{competitor_id}")
async def get_ads_stats(
    competitor_id: int,
    db: Session = Depends(get_db),
):
    """Statistiques publicitaires d'un concurrent."""
    competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    ads = db.query(Ad).filter(Ad.competitor_id == competitor_id).all()
    active_ads = [a for a in ads if a.is_active]

    # Platform breakdown
    platform_counts = {}
    for ad in ads:
        platform_counts[ad.platform] = platform_counts.get(ad.platform, 0) + 1

    # Spend
    total_spend_min = sum(a.estimated_spend_min or 0 for a in ads)
    total_spend_max = sum(a.estimated_spend_max or 0 for a in ads)

    # Monthly trend
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    recent_ads = [a for a in ads if a.start_date and a.start_date > six_months_ago]
    monthly_trend = {}
    for ad in recent_ads:
        month_key = ad.start_date.strftime("%Y-%m")
        monthly_trend[month_key] = monthly_trend.get(month_key, 0) + 1

    return {
        "competitor_id": competitor_id,
        "competitor_name": competitor.name,
        "total_ads_tracked": len(ads),
        "active_ads": len(active_ads),
        "platform_breakdown": platform_counts,
        "estimated_total_spend": {
            "min": total_spend_min,
            "max": total_spend_max,
            "currency": "EUR",
        },
        "monthly_trend": monthly_trend,
    }


@router.get("/comparison")
async def compare_competitors_ads(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Compare les activités publicitaires des concurrents de l'utilisateur."""
    comp_query = db.query(Competitor).filter(Competitor.is_active == True)
    if user:
        comp_query = comp_query.filter(Competitor.user_id == user.id)
    competitors = comp_query.all()

    items = []
    for comp in competitors:
        ads = db.query(Ad).filter(Ad.competitor_id == comp.id).all()
        active = [a for a in ads if a.is_active]

        items.append({
            "competitor_id": comp.id,
            "competitor_name": comp.name,
            "total_ads": len(ads),
            "active_ads": len(active),
            "total_spend_min": sum(a.estimated_spend_min or 0 for a in ads),
            "total_spend_max": sum(a.estimated_spend_max or 0 for a in ads),
        })

    items.sort(key=lambda x: x["total_ads"], reverse=True)
    return items


# =============================================================================
# Helpers
# =============================================================================

def _parse_json(value: str) -> list:
    """Parse a JSON string to list, or return empty list."""
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def _name_matches(competitor_name: str, page_name: str) -> bool:
    """Check if a page name matches the competitor (fuzzy)."""
    c = competitor_name.lower().strip()
    p = page_name.lower().strip()
    return c in p or p in c or c.split()[0] in p


def _parse_date(date_str) -> Optional[datetime]:
    """Parse date from various formats."""
    if not date_str:
        return None
    if isinstance(date_str, int):
        return datetime.fromtimestamp(date_str)
    try:
        return datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None

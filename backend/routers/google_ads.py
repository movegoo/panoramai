"""
Google Ads Transparency - Collect ads from Google Ads Transparency Center.
Uses ScrapeCreators /v1/google/company/ads endpoint.
"""
import json
import logging
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db, Competitor, Ad, User
from services.scrapecreators import scrapecreators
from core.auth import get_current_user
from core.permissions import verify_competitor_ownership, get_user_competitors, parse_advertiser_header

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_domain(website: str) -> str | None:
    """Extract clean domain from a website URL."""
    if not website:
        return None
    if not website.startswith("http"):
        website = "https://" + website
    try:
        parsed = urlparse(website)
        domain = parsed.hostname or ""
        # Remove www.
        if domain.startswith("www."):
            domain = domain[4:]
        return domain if domain else None
    except Exception:
        return None


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse ISO date string."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


@router.get("/ads/all")
async def get_all_google_ads(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Liste toutes les pubs Google avec le nom du concurrent."""
    query = db.query(Ad, Competitor.name).join(
        Competitor, Ad.competitor_id == Competitor.id
    ).filter(Ad.platform == "google")

    from core.permissions import get_user_competitor_ids
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp_id_list = get_user_competitor_ids(db, user, advertiser_id=adv_id)
    query = query.filter(Competitor.id.in_(comp_id_list))
    if active_only:
        query = query.filter(Ad.is_active == True)

    rows = query.order_by(desc(Ad.start_date)).limit(3000).all()

    results = []
    for ad, comp_name in rows:
        countries = []
        if ad.targeted_countries:
            try:
                countries = json.loads(ad.targeted_countries) if isinstance(ad.targeted_countries, str) else ad.targeted_countries
            except (json.JSONDecodeError, TypeError):
                pass
        results.append({
            "id": ad.id,
            "ad_id": ad.ad_id,
            "competitor_id": ad.competitor_id,
            "competitor_name": comp_name,
            "platform": "google",
            "creative_url": ad.creative_url,
            "ad_text": ad.ad_text,
            "cta": ad.cta,
            "start_date": ad.start_date.isoformat() if ad.start_date else None,
            "end_date": ad.end_date.isoformat() if ad.end_date else None,
            "is_active": ad.is_active,
            "page_name": ad.page_name,
            "display_format": ad.display_format,
            "ad_library_url": ad.ad_library_url,
            "link_url": ad.link_url,
            "targeted_countries": countries,
            "publisher_platforms": ["GOOGLE"],
            "impressions_min": ad.impressions_min,
            "impressions_max": ad.impressions_max,
            # Creative Analysis
            "creative_concept": ad.creative_concept,
            "creative_hook": ad.creative_hook,
            "creative_tone": ad.creative_tone,
            "creative_dominant_colors": json.loads(ad.creative_dominant_colors) if ad.creative_dominant_colors else None,
            "creative_has_product": ad.creative_has_product,
            "creative_has_face": ad.creative_has_face,
            "creative_has_logo": ad.creative_has_logo,
            "creative_layout": ad.creative_layout,
            "creative_cta_style": ad.creative_cta_style,
            "creative_score": ad.creative_score,
            "creative_tags": json.loads(ad.creative_tags) if ad.creative_tags else None,
            "creative_summary": ad.creative_summary,
            "creative_analyzed_at": ad.creative_analyzed_at.isoformat() if ad.creative_analyzed_at else None,
        })

    return results


@router.get("/ads/{competitor_id}")
async def get_google_ads(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Liste les pubs Google collectees pour un concurrent."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitor = verify_competitor_ownership(db, competitor_id, user, advertiser_id=adv_id)

    ads = db.query(Ad).filter(
        Ad.competitor_id == competitor_id,
        Ad.platform == "google",
    ).all()

    return {
        "competitor": competitor.name,
        "total": len(ads),
        "ads": [
            {
                "id": ad.id,
                "ad_id": ad.ad_id,
                "advertiser_name": ad.page_name,
                "format": ad.display_format,
                "image_url": ad.creative_url,
                "ad_url": ad.ad_library_url,
                "first_shown": ad.start_date.isoformat() if ad.start_date else None,
                "last_shown": ad.end_date.isoformat() if ad.end_date else None,
                "is_active": ad.is_active,
            }
            for ad in ads
        ],
    }


@router.post("/fetch/{competitor_id}")
async def fetch_google_ads(
    competitor_id: int,
    country: str = Query("FR", description="Pays cible"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Collecte les pubs Google d'un concurrent via Google Ads Transparency Center.
    Utilise le domaine du site web du concurrent.
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitor = verify_competitor_ownership(db, competitor_id, user, advertiser_id=adv_id)

    domain = _extract_domain(competitor.website)
    if not domain:
        raise HTTPException(
            status_code=400,
            detail=f"Pas de domaine web pour '{competitor.name}'. Renseignez le site web d'abord."
        )

    new_count, updated_count, total_fetched = await _fetch_and_store_google_ads(
        competitor_id=competitor_id,
        domain=domain,
        country=country,
        db=db,
    )

    return {
        "competitor": competitor.name,
        "domain": domain,
        "fetched": total_fetched,
        "new": new_count,
        "updated": updated_count,
    }


async def _fetch_and_store_google_ads(
    competitor_id: int,
    domain: str,
    country: str,
    db: Session,
    max_pages: int = 3,
) -> tuple[int, int, int]:
    """Fetch Google Ads and store them. Returns (new, updated, total_fetched)."""
    new_count = 0
    updated_count = 0
    total_fetched = 0
    cursor = None

    for _ in range(max_pages):
        result = await scrapecreators.search_google_ads(
            domain=domain, country=country, cursor=cursor
        )

        if not result.get("success"):
            logger.warning(f"Google Ads API error for {domain}: {result.get('error')}")
            break

        ads = result.get("ads", [])
        if not ads:
            break

        total_fetched += len(ads)

        for ad in ads:
            creative_id = ad.get("creativeId", "")
            if not creative_id:
                continue

            # Check if already exists
            existing = db.query(Ad).filter(Ad.ad_id == creative_id).first()

            first_shown = _parse_date(ad.get("firstShown"))
            last_shown = _parse_date(ad.get("lastShown"))

            # Consider active if last shown within the last 7 days
            is_active = False
            if last_shown:
                is_active = (datetime.utcnow() - last_shown.replace(tzinfo=None)).days <= 7

            # Parse impressions if available
            impressions = ad.get("overallImpressions") or {}
            imp_min = impressions.get("min") if isinstance(impressions, dict) else None
            imp_max = impressions.get("max") if isinstance(impressions, dict) else None

            if existing:
                # Update last_shown and active status
                existing.end_date = last_shown
                existing.is_active = is_active
                if imp_min is not None:
                    existing.impressions_min = imp_min
                if imp_max is not None:
                    existing.impressions_max = imp_max
                updated_count += 1
            else:
                new_ad = Ad(
                    competitor_id=competitor_id,
                    ad_id=creative_id,
                    platform="google",
                    creative_url=ad.get("imageUrl") or "",
                    ad_text="",
                    cta="",
                    start_date=first_shown,
                    end_date=last_shown,
                    is_active=is_active,
                    impressions_min=imp_min,
                    impressions_max=imp_max,
                    page_name=ad.get("advertiserName") or "",
                    display_format=(ad.get("format") or "").upper(),
                    ad_library_url=ad.get("adUrl") or "",
                    link_url=f"https://{domain}",
                    targeted_countries=json.dumps([country]) if country else None,
                )
                db.add(new_ad)
                new_count += 1

        cursor = result.get("cursor")
        if not cursor:
            break

    db.commit()
    logger.info(f"Google Ads: {new_count} new, {updated_count} updated for domain={domain}")
    return new_count, updated_count, total_fetched


@router.post("/fetch-all")
async def fetch_all_google_ads(
    country: str = Query("FR"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Collecte les pubs Google pour tous les concurrents."""
    competitors = get_user_competitors(db, user, advertiser_id=int(x_advertiser_id) if x_advertiser_id else None)
    results = []

    for comp in competitors:
        domain = _extract_domain(comp.website)
        if not domain:
            results.append({"competitor": comp.name, "skipped": "no domain"})
            continue

        try:
            new, updated, fetched = await _fetch_and_store_google_ads(
                competitor_id=comp.id, domain=domain, country=country, db=db
            )
            results.append({
                "competitor": comp.name,
                "domain": domain,
                "fetched": fetched,
                "new": new,
                "updated": updated,
            })
        except Exception as e:
            logger.error(f"Google Ads fetch failed for {comp.name}: {e}")
            results.append({"competitor": comp.name, "error": str(e)})

    return {
        "message": f"Google Ads collected for {len(competitors)} competitors",
        "results": results,
    }

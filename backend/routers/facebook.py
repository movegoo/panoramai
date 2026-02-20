"""
Meta Ads Router.
Veille publicitaire concurrentielle via ScrapeCreators Ad Library API.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional
from datetime import datetime, timedelta
import json
import asyncio
import logging

from database import get_db, SessionLocal, Competitor, Ad, User, StoreLocation
from core.auth import get_current_user
from core.permissions import verify_competitor_ownership, get_user_competitors, get_user_competitor_ids, parse_advertiser_header
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
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Retourne TOUTES les publicités des concurrents actifs."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)
    active_comps = {c.id: c.name for c in competitors}

    query = db.query(Ad).filter(
        Ad.competitor_id.in_(active_comps.keys()),
        Ad.platform.in_(["facebook", "instagram"]),
    )
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
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Retourne les publicités stockées pour un concurrent.
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    verify_competitor_ownership(db, competitor_id, user, advertiser_id=adv_id)

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
        "payer": ad.payer,
        "beneficiary": ad.beneficiary,
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
        "ad_type": ad.ad_type,
    }


@router.post("/resolve-page-ids")
async def resolve_facebook_page_ids(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Auto-detect missing facebook_page_id for all competitors.
    Uses ScrapeCreators search/companies endpoint.
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)

    resolved = []
    errors = []

    for comp in competitors:
        if comp.facebook_page_id:
            resolved.append({"id": comp.id, "name": comp.name, "page_id": comp.facebook_page_id, "status": "already_set"})
            continue

        result = await scrapecreators.search_facebook_companies(comp.name)
        if not result.get("success") or not result.get("companies"):
            errors.append({"id": comp.id, "name": comp.name, "error": "No company found"})
            continue

        # Pick the best match (first result or name match)
        companies = result["companies"]
        best = None
        for c in companies:
            c_name = (c.get("page_name") or c.get("name") or "").lower()
            if comp.name.lower() in c_name or c_name in comp.name.lower():
                best = c
                break
        if not best and companies:
            best = companies[0]

        page_id = str(best.get("page_id") or best.get("pageId") or best.get("id") or "")
        page_name = best.get("page_name") or best.get("name") or ""

        if page_id:
            comp.facebook_page_id = page_id
            resolved.append({"id": comp.id, "name": comp.name, "page_id": page_id, "page_name": page_name, "status": "resolved"})
        else:
            errors.append({"id": comp.id, "name": comp.name, "error": "No page_id in result"})

    db.commit()

    return {
        "message": f"Resolved {sum(1 for r in resolved if r['status'] == 'resolved')} page IDs",
        "resolved": resolved,
        "errors": errors,
    }


# ── Child page discovery constants (module-level) ──
FALLBACK_CITIES = [
    "Paris", "Lyon", "Marseille", "Toulouse", "Nice", "Nantes",
    "Strasbourg", "Montpellier", "Bordeaux", "Lille",
]

BRAND_PREFIXES: dict[str, list[str]] = {
    "carrefour": ["carrefour"],
    "leclerc": ["e.leclerc", "leclerc", "e leclerc"],
    "lidl": ["lidl"],
    "auchan": ["auchan"],
    "intermarche": ["intermarché", "intermarche"],
    "monoprix": ["monoprix", "monop'"],
    "casino": ["casino #bio", "casino supermarché", "casino supermarche", "casino shop", "géant casino", "geant casino", "casino max", "casino proximité"],
    "systeme u": ["super u", "hyper u", "u express"],
    "ikea": ["ikea"],
    "decathlon": ["decathlon"],
    "leroy merlin": ["leroy merlin"],
    "sephora": ["sephora"],
    "hermès": ["hermès", "hermes"],
    "picard": ["picard"],
    "aldi": ["aldi"],
    "franprix": ["franprix"],
    "action": ["action"],
    "fnac": ["fnac"],
    "darty": ["darty"],
    "grand frais": ["grand frais"],
}

NEGATIVE_KEYWORDS = [
    "barrière", "barriere", "café de paris", "serrures", "hypnothérapeute",
    "hypnotherapeute", "parish council", "conseil municipal", "musée",
    "museum", "théâtre", "theatre", "cinéma", "cinema", "fondation",
    "association", "festival", "qatar", "argentina", " uk", "hrvatska",
    "belgique", "españa", "italia", "deutschland",
]

# In-memory progress tracking for background discovery
_discovery_status: dict[str, dict] = {}


def _is_valid_child(brand_name: str, page_name: str) -> bool:
    """Check if page_name starts with a known prefix for this brand (word boundary)."""
    pn = page_name.lower().strip()
    bn = brand_name.lower().strip()

    for neg in NEGATIVE_KEYWORDS:
        if neg in pn:
            return False

    matched_prefixes = None
    for key, prefixes in BRAND_PREFIXES.items():
        if key in bn or bn in key:
            matched_prefixes = prefixes
            break

    check_prefixes = matched_prefixes or [bn]

    for prefix in check_prefixes:
        if pn.startswith(prefix):
            rest = pn[len(prefix):]
            if rest == "" or rest[0] in " -_.'&,/()":
                return True
    return False


async def _discover_child_pages_background(competitor_ids: list[int], advertiser_id: int):
    """Background task: discover child Facebook pages using BANCO cities."""
    from database import SessionLocal

    task_id = f"discover-{datetime.utcnow().strftime('%H%M%S')}"
    _discovery_status[task_id] = {"status": "running", "started": datetime.utcnow().isoformat(), "results": []}

    db = SessionLocal()
    try:
        competitors = db.query(Competitor).filter(Competitor.id.in_(competitor_ids)).all()
        total_found = 0

        for comp in competitors:
            parent_page_id = comp.facebook_page_id or ""
            existing_children = set()
            found_children = []

            # Strategy 1: Mine existing ads
            ads_with_pages = db.query(Ad.page_id, Ad.page_name).filter(
                Ad.competitor_id == comp.id,
                Ad.page_id.isnot(None),
                Ad.page_name.isnot(None),
            ).distinct().all()

            for ad_page_id, ad_page_name in ads_with_pages:
                if not ad_page_id or ad_page_id == parent_page_id:
                    continue
                if ad_page_id in existing_children:
                    continue
                if _is_valid_child(comp.name, ad_page_name or ""):
                    existing_children.add(ad_page_id)
                    found_children.append({"page_id": ad_page_id, "page_name": ad_page_name, "source": "ads_db"})

            # Strategy 2: BANCO cities
            banco_cities = (
                db.query(StoreLocation.city)
                .filter(StoreLocation.competitor_id == comp.id, StoreLocation.city.isnot(None))
                .group_by(StoreLocation.city)
                .order_by(func.count(StoreLocation.id).desc())
                .all()
            )
            cities = [row[0] for row in banco_cities if row[0] and len(row[0]) > 1]
            if not cities:
                cities = FALLBACK_CITIES

            logger.info(f"[{comp.name}] Searching {len(cities)} BANCO cities for child pages")
            _discovery_status[task_id][comp.name] = {"total_cities": len(cities), "processed": 0, "found": 0}

            for i, city in enumerate(cities):
                query = f"{comp.name} {city}"
                try:
                    search_result = await scrapecreators.search_facebook_companies(query)
                    if search_result.get("success"):
                        for company in search_result.get("companies", []):
                            page_id = str(company.get("page_id") or company.get("pageId") or company.get("id") or "")
                            page_name = company.get("page_name") or company.get("name") or ""
                            if not page_id or page_id == parent_page_id or page_id in existing_children:
                                continue
                            if _is_valid_child(comp.name, page_name):
                                existing_children.add(page_id)
                                found_children.append({"page_id": page_id, "page_name": page_name, "source": f"search:{query}"})
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.warning(f"Child page search failed for '{query}': {e}")

                if (i + 1) % 50 == 0:
                    _discovery_status[task_id][comp.name]["processed"] = i + 1
                    _discovery_status[task_id][comp.name]["found"] = len(found_children)
                    logger.info(f"[{comp.name}] Progress: {i+1}/{len(cities)} cities, {len(found_children)} pages found")

            # Save
            if existing_children:
                comp.child_page_ids = json.dumps(list(existing_children))

            result = {
                "competitor_id": comp.id,
                "competitor_name": comp.name,
                "cities_searched": len(cities),
                "new_children_found": len(found_children),
                "total_children": len(existing_children),
            }
            _discovery_status[task_id]["results"].append(result)
            total_found += len(found_children)
            logger.info(f"[{comp.name}] Done: {len(found_children)} child pages found from {len(cities)} cities")

            db.commit()

        _discovery_status[task_id]["status"] = "completed"
        _discovery_status[task_id]["total_found"] = total_found
        logger.info(f"Discovery complete: {total_found} total child pages across {len(competitors)} competitors")

    except Exception as e:
        logger.error(f"Discovery background task failed: {e}")
        _discovery_status[task_id]["status"] = f"error: {e}"
    finally:
        db.close()


@router.post("/discover-child-pages")
async def discover_child_pages(
    competitor_id: int | None = Query(None, description="Process a single competitor"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Launch background discovery of child/local Facebook pages using BANCO store cities.
    Returns immediately — check progress via GET /api/facebook/discover-child-pages/status.
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)

    if competitor_id:
        competitors = [c for c in competitors if c.id == competitor_id]
        if not competitors:
            raise HTTPException(404, "Competitor not found")

    comp_ids = [c.id for c in competitors]
    comp_names = [c.name for c in competitors]

    # Count cities per competitor for the response
    city_counts = {}
    for comp in competitors:
        count = db.query(func.count(func.distinct(StoreLocation.city))).filter(
            StoreLocation.competitor_id == comp.id, StoreLocation.city.isnot(None)
        ).scalar() or 0
        city_counts[comp.name] = count if count > 0 else len(FALLBACK_CITIES)

    # Launch background task
    asyncio.create_task(_discover_child_pages_background(comp_ids, adv_id))

    return {
        "message": f"Discovery launched in background for {len(competitors)} competitors",
        "competitors": comp_names,
        "cities_to_search": city_counts,
        "total_api_calls": sum(city_counts.values()),
        "estimated_time_minutes": round(sum(city_counts.values()) * 0.5 / 60, 1),
        "check_progress": "GET /api/facebook/discover-child-pages/status",
    }


@router.get("/discover-child-pages/status")
async def discover_child_pages_status():
    """Check progress of background child page discovery."""
    if not _discovery_status:
        return {"message": "No discovery task running or completed"}
    # Return the most recent task
    latest_key = list(_discovery_status.keys())[-1]
    return _discovery_status[latest_key]


@router.get("/child-pages")
async def list_child_pages(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """List all competitors and their child page IDs."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)

    result = []
    for comp in competitors:
        children = []
        if comp.child_page_ids:
            try:
                children = json.loads(comp.child_page_ids)
            except (json.JSONDecodeError, TypeError):
                pass

        result.append({
            "competitor_id": comp.id,
            "name": comp.name,
            "facebook_page_id": comp.facebook_page_id,
            "child_page_ids": children,
            "child_count": len(children),
        })

    return result


@router.post("/fetch/{competitor_id}")
async def fetch_competitor_ads(
    competitor_id: int,
    country: str = Query("FR", description="Pays de diffusion"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Récupère les publicités d'un concurrent via ScrapeCreators Ad Library.
    Utilise le facebook_page_id si disponible (company/ads endpoint),
    sinon fait une recherche par nom puis auto-resolve le page_id.
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitor = verify_competitor_ownership(db, competitor_id, user, advertiser_id=adv_id)

    use_page_id = False
    page_id_used = competitor.facebook_page_id

    # Strategy 1: Use page_id if available (most reliable) — with pagination
    if page_id_used:
        all_ads = []
        cursor = None
        max_pages = 30  # Safety limit (~300 ads max)
        for _ in range(max_pages):
            result = await scrapecreators.fetch_facebook_company_ads(
                page_id=page_id_used,
                cursor=cursor,
            )
            if not result.get("success"):
                break
            batch = result.get("ads", [])
            all_ads.extend(batch)
            cursor = result.get("cursor")
            if not cursor or not batch:
                break
        if all_ads:
            use_page_id = True
            result = {"success": True, "ads": all_ads}

    # Strategy 2: Auto-resolve page_id via company search
    if not use_page_id and not page_id_used:
        search_result = await scrapecreators.search_facebook_companies(competitor.name)
        if search_result.get("success") and search_result.get("companies"):
            companies = search_result["companies"]
            best = None
            for c in companies:
                c_name = (c.get("page_name") or c.get("name") or "").lower()
                if competitor.name.lower() in c_name or c_name in competitor.name.lower():
                    best = c
                    break
            if not best and companies:
                best = companies[0]

            resolved_id = str(best.get("page_id") or best.get("pageId") or best.get("id") or "") if best else ""
            if resolved_id:
                # Save the resolved page_id
                competitor.facebook_page_id = resolved_id
                page_id_used = resolved_id
                db.commit()
                logger.info(f"Auto-resolved facebook_page_id={resolved_id} for {competitor.name}")

                # Paginated fetch for resolved page too
                all_ads = []
                cursor = None
                for _ in range(30):
                    result = await scrapecreators.fetch_facebook_company_ads(
                        page_id=resolved_id,
                        cursor=cursor,
                    )
                    if not result.get("success"):
                        break
                    batch = result.get("ads", [])
                    all_ads.extend(batch)
                    cursor = result.get("cursor")
                    if not cursor or not batch:
                        break
                if all_ads:
                    use_page_id = True
                    result = {"success": True, "ads": all_ads}

    # Strategy 3: Fallback to keyword search
    if not use_page_id:
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

        # When using page_id, all ads belong to this competitor (no fuzzy match needed)
        # When using keyword search, filter by name match
        if not use_page_id and not _name_matches(competitor.name, page_name_val):
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

        # Auto-fill competitor's facebook_page_id from first ad if missing
        if page_id and not competitor.facebook_page_id:
            competitor.facebook_page_id = page_id
            logger.info(f"Auto-filled facebook_page_id={page_id} for {competitor.name} from ad data")

        # Classify ad type
        ad_type = _classify_ad_type(link_url, None, cta, display_format)

        # Common fields dict
        enriched = dict(
            platform=platform,
            ad_type=ad_type,
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

    # Fetch child pages (pages filles) — aggregate into parent competitor
    child_new = 0
    child_page_ids_list = []
    if competitor.child_page_ids:
        try:
            child_page_ids_list = json.loads(competitor.child_page_ids)
        except (json.JSONDecodeError, TypeError):
            child_page_ids_list = []

    for child_id in child_page_ids_list:
        child_id = str(child_id).strip()
        if not child_id:
            continue
        try:
            # Paginated fetch for child pages too
            child_ads = []
            cursor = None
            for _ in range(30):
                child_result = await scrapecreators.fetch_facebook_company_ads(page_id=child_id, cursor=cursor)
                if not child_result.get("success"):
                    break
                batch = child_result.get("ads", [])
                child_ads.extend(batch)
                cursor = child_result.get("cursor")
                if not cursor or not batch:
                    break
            for ad in child_ads:
                ad_id = str(ad.get("ad_archive_id", ""))
                if not ad_id:
                    continue
                if db.query(Ad).filter(Ad.ad_id == ad_id).first():
                    continue
                snapshot = ad.get("snapshot", {})
                cards = snapshot.get("cards", [])
                first_card = cards[0] if cards else {}
                ad_text = first_card.get("body") or snapshot.get("body", {}).get("text", "") or ""
                cta = first_card.get("cta_text") or snapshot.get("cta_text", "")
                creative_url = first_card.get("original_image_url") or first_card.get("resized_image_url") or ""
                start_date = _parse_date(ad.get("start_date_string") or ad.get("start_date"))
                end_date = _parse_date(ad.get("end_date_string") or ad.get("end_date"))
                link_url_val = first_card.get("link_url") or snapshot.get("link_url", "")
                display_fmt = snapshot.get("display_format", "")
                ad_type = _classify_ad_type(link_url_val, None, cta, display_fmt)
                pubs = ad.get("publisher_platform", [])
                if not isinstance(pubs, list):
                    pubs = [pubs] if pubs else []
                platform = "facebook"
                for p in pubs:
                    if "INSTAGRAM" in str(p).upper():
                        platform = "instagram"
                        break
                new_ad = Ad(
                    competitor_id=competitor_id,
                    ad_id=ad_id,
                    platform=platform,
                    ad_type=ad_type,
                    creative_url=creative_url,
                    ad_text=ad_text,
                    cta=cta,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=ad.get("is_active", not bool(end_date)),
                    page_name=snapshot.get("page_name", "") or None,
                    page_id=child_id,
                    link_url=link_url_val or None,
                    display_format=display_fmt or None,
                    ad_library_url=ad.get("url", "") or None,
                )
                db.add(new_ad)
                child_new += 1
            db.commit()
        except Exception as e:
            logger.warning(f"Child page {child_id} fetch failed: {e}")

    return {
        "message": f"Fetched {len(ads_data)} ads for {competitor.name}" + (f" + {child_new} from child pages" if child_new else ""),
        "total_fetched": len(ads_data),
        "new_stored": new_count,
        "updated": updated_count,
        "child_pages_new": child_new,
        "total_available": result.get("total_available", len(ads_data)),
        "method": "page_id" if use_page_id else "keyword_search",
        "facebook_page_id": page_id_used,
    }


@router.post("/enrich-transparency")
async def enrich_ads_transparency(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Enrich all Meta ads that lack EU transparency data (age, gender, location, reach)
    by fetching individual ad details from the Ad Library.
    Uses concurrent requests for speed (batches of 10, max 25 ads per call).
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    user_comp_ids = get_user_competitor_ids(db, user, advertiser_id=adv_id)

    # Only enrich Meta/Facebook ads (not TikTok/Google)
    meta_platforms = ["facebook", "instagram", "messenger", "audience_network", "meta",
                      "FACEBOOK", "INSTAGRAM", "MESSENGER", "AUDIENCE_NETWORK", "META"]
    ads_to_enrich = db.query(Ad).filter(
        Ad.eu_total_reach.is_(None),
        Ad.platform.in_(meta_platforms),
        Ad.competitor_id.in_(user_comp_ids),
    ).limit(25).all()

    if not ads_to_enrich:
        return {"message": "All Meta ads already enriched", "enriched": 0, "total_meta": 0}

    enriched_count = 0
    errors = 0

    async def _enrich_one(ad):
        try:
            detail = await scrapecreators.get_facebook_ad_detail(ad.ad_id)
            if not detail.get("success"):
                ad.eu_total_reach = 0
                return False
            ad.age_min = detail.get("age_min")
            ad.age_max = detail.get("age_max")
            ad.gender_audience = detail.get("gender_audience")
            ad.eu_total_reach = detail.get("eu_total_reach") or 0
            loc = detail.get("location_audience", [])
            if loc:
                ad.location_audience = json.dumps(loc)
            breakdown = detail.get("age_country_gender_reach_breakdown", [])
            if breakdown:
                ad.age_country_gender_reach = json.dumps(breakdown)
            # Save payer/byline if available (rare from ScrapeCreators but possible)
            byline = detail.get("byline")
            if byline:
                ad.byline = byline
            # Store payer/beneficiary if ScrapeCreators provides them
            payer = detail.get("payer")
            beneficiary_val = detail.get("beneficiary")
            if payer:
                ad.payer = payer
            if beneficiary_val:
                ad.beneficiary = beneficiary_val
            return True
        except Exception as e:
            logger.error(f"Error enriching ad {ad.ad_id}: {e}")
            ad.eu_total_reach = 0
            return False

    # Process in concurrent batches of 10
    BATCH_SIZE = 10
    for i in range(0, len(ads_to_enrich), BATCH_SIZE):
        batch = ads_to_enrich[i:i + BATCH_SIZE]
        results = await asyncio.gather(*[_enrich_one(ad) for ad in batch])
        enriched_count += sum(1 for r in results if r)
        errors += sum(1 for r in results if not r)
        # Commit after each batch to save progress
        db.commit()

    return {
        "message": f"Enriched {enriched_count} ads with EU transparency data",
        "enriched": enriched_count,
        "errors": errors,
        "total_meta_ads": len(ads_to_enrich),
    }


@router.get("/ad-detail-raw/{ad_archive_id}")
async def get_ad_detail_raw(
    ad_archive_id: str,
    user: User = Depends(get_current_user),
):
    """Debug: return raw ScrapeCreators response for a single ad."""
    data = await scrapecreators.get_facebook_ad_detail_raw(ad_archive_id)
    return data


@router.post("/enrich-payers")
async def enrich_payers(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Enrich Meta ads with payer/beneficiary data from the official Meta Ad Library API.
    ScrapeCreators doesn't return this data, but the official API provides it
    via the 'beneficiary_payers' and 'bylines' fields (EU DSA requirement).
    """
    from services.meta_api import meta_api

    if not meta_api.is_configured:
        raise HTTPException(status_code=503, detail="META_ACCESS_TOKEN not configured. Set it in Railway env vars.")

    adv_id = parse_advertiser_header(x_advertiser_id)
    user_comp_ids = get_user_competitor_ids(db, user, advertiser_id=adv_id)

    # Get competitors with facebook_page_id
    competitors = db.query(Competitor).filter(
        Competitor.id.in_(user_comp_ids),
        Competitor.facebook_page_id.isnot(None),
    ).all()

    if not competitors:
        raise HTTPException(status_code=404, detail="No competitors with facebook_page_id found")

    total_updated = 0
    results = []

    for comp in competitors:
        try:
            # Fetch ads from official Meta API (which includes beneficiary_payers)
            api_result = await meta_api.search_ads_library(
                page_id=comp.facebook_page_id,
                countries="FR",
                limit=100,
            )

            # Check for API errors
            if "error" in api_result:
                results.append({
                    "competitor": comp.name,
                    "error": str(api_result["error"]),
                })
                continue

            api_ads = api_result.get("data", [])
            comp_updated = 0

            for api_ad in api_ads:
                ad_id = str(api_ad.get("id", ""))
                if not ad_id:
                    continue

                # Find matching ad in our DB
                db_ad = db.query(Ad).filter(Ad.ad_id == ad_id, Ad.competitor_id == comp.id).first()
                if not db_ad:
                    continue

                # Extract payer from beneficiary_payers
                bp = api_ad.get("beneficiary_payers", [])
                if bp and isinstance(bp, list) and len(bp) > 0:
                    first_bp = bp[0] if isinstance(bp[0], dict) else {}
                    payer = first_bp.get("payer", "")
                    beneficiary = first_bp.get("beneficiary", "")
                    # Use payer first, fall back to beneficiary
                    payer_name = payer or beneficiary
                    if payer_name and not db_ad.byline:
                        db_ad.byline = payer_name
                        comp_updated += 1

                # Also check bylines field
                bylines = api_ad.get("bylines", [])
                if bylines and isinstance(bylines, list) and not db_ad.disclaimer_label:
                    db_ad.disclaimer_label = bylines[0] if bylines else None

            if comp_updated:
                db.commit()
                total_updated += comp_updated

            results.append({
                "competitor": comp.name,
                "page_id": comp.facebook_page_id,
                "api_ads_found": len(api_ads),
                "payers_updated": comp_updated,
            })

        except Exception as e:
            results.append({
                "competitor": comp.name,
                "error": str(e),
            })

    return {
        "message": f"Updated payer info for {total_updated} ads",
        "total_updated": total_updated,
        "details": results,
    }


@router.post("/enrich-payers-searchapi")
async def enrich_payers_searchapi(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Enrich Meta ads with payer/beneficiary data via SearchAPI.io.
    Targets ALL ads that have been enriched by ScrapeCreators (eu_total_reach IS NOT NULL)
    but still lack payer info.
    """
    from services.searchapi import searchapi

    if not searchapi.is_configured:
        raise HTTPException(status_code=503, detail="SEARCHAPI_KEY not configured")

    adv_id = parse_advertiser_header(x_advertiser_id)
    user_comp_ids = get_user_competitor_ids(db, user, advertiser_id=adv_id)

    # Select Meta ads already enriched by ScrapeCreators but missing payer
    meta_platforms = ["facebook", "instagram"]
    ads_to_enrich = db.query(Ad).filter(
        Ad.payer.is_(None),
        Ad.eu_total_reach.isnot(None),
        Ad.platform.in_(meta_platforms),
        Ad.competitor_id.in_(user_comp_ids),
    ).all()

    if not ads_to_enrich:
        return {"message": "All Meta ads already have payer data", "enriched": 0}

    enriched_count = 0
    errors = 0

    for ad in ads_to_enrich:
        try:
            result = await searchapi.get_ad_details(ad.ad_id)
            if not result.get("success"):
                errors += 1
                continue

            payer = result.get("payer")
            beneficiary = result.get("beneficiary")

            if payer:
                ad.payer = payer
            if beneficiary:
                ad.beneficiary = beneficiary

            # Fallback: update eu_total_reach if ScrapeCreators returned 0
            searchapi_reach = result.get("eu_total_reach")
            if ad.eu_total_reach == 0 and searchapi_reach and searchapi_reach > 0:
                ad.eu_total_reach = searchapi_reach

            if payer or beneficiary:
                enriched_count += 1
        except Exception as e:
            logger.error(f"SearchAPI error for ad {ad.ad_id}: {e}")
            errors += 1

        # Commit every 20 ads to save progress
        if (enriched_count + errors) % 20 == 0:
            db.commit()

    db.commit()

    return {
        "message": f"Enriched {enriched_count}/{len(ads_to_enrich)} ads with payer/beneficiary via SearchAPI",
        "enriched": enriched_count,
        "errors": errors,
        "total_processed": len(ads_to_enrich),
    }


@router.get("/stats/{competitor_id}")
async def get_ads_stats(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Statistiques publicitaires d'un concurrent."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitor = verify_competitor_ownership(db, competitor_id, user, advertiser_id=adv_id)

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
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Compare les activités publicitaires des concurrents de l'utilisateur."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)

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

import re

def _classify_ad_type(link_url: str | None, creative_concept: str | None, cta: str | None, display_format: str | None) -> str:
    """Classify an ad as branding, performance, or dts (drive-to-store)."""
    link = (link_url or "").lower()
    cta_lower = (cta or "").lower()
    concept = (creative_concept or "").lower()
    fmt = (display_format or "").upper()

    # DPA = always performance
    if fmt == "DPA":
        return "performance"

    # Drive-to-Store signals
    dts_url_patterns = [
        r"store.?locator", r"magasin", r"maps\.google", r"google\.com/maps",
        r"trouver.?magasin", r"point.?de.?vente", r"boutique.?pres",
    ]
    dts_cta_patterns = [
        r"trouver", r"itin[eé]raire", r"magasin", r"store",
        r"get.?directions", r"find.?store", r"localiser",
    ]
    for pat in dts_url_patterns:
        if re.search(pat, link):
            return "dts"
    for pat in dts_cta_patterns:
        if re.search(pat, cta_lower):
            return "dts"

    # Performance signals
    perf_url_patterns = [
        r"/product", r"/shop", r"/cart", r"/panier", r"/checkout",
        r"\?utm_", r"/collection", r"/catalogue", r"/promo",
    ]
    perf_cta_patterns = [
        r"acheter", r"commander", r"shop.?now", r"buy",
        r"ajouter.?au.?panier", r"add.?to.?cart", r"en.?savoir.?plus",
        r"voir.?l.?offre", r"profiter", r"d[eé]couvrir.?l.?offre",
    ]
    for pat in perf_url_patterns:
        if re.search(pat, link):
            return "performance"
    for pat in perf_cta_patterns:
        if re.search(pat, cta_lower):
            return "performance"

    # Everything else = branding
    return "branding"


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

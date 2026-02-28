"""
Mon Enseigne - Brand management router.
Central entity representing the user's retail brand.
"""
import re
import logging
import base64
from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db, Advertiser, Competitor, User, AdvertiserCompetitor, UserAdvertiser
from models.schemas import BrandSetup
from core.sectors import get_sector_label, get_competitors_for_sector, list_sectors, SECTORS
from core.auth import get_current_user, get_optional_user, get_current_advertiser
from core.utils import get_logo_url
from core.permissions import parse_advertiser_header

logger = logging.getLogger(__name__)

router = APIRouter()


def count_configured_channels(brand: Advertiser) -> int:
    """Compte le nombre de canaux configurés."""
    channels = [
        brand.playstore_app_id,
        brand.appstore_app_id,
        brand.instagram_username,
        brand.tiktok_username,
        brand.youtube_channel_id,
    ]
    return sum(1 for c in channels if c)


def get_current_brand(db: Session, user: User | None = None, advertiser_id: int | None = None) -> Advertiser:
    """Récupère l'enseigne courante via user_advertisers join table."""
    if user:
        user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
        if not user_adv_ids:
            raise HTTPException(status_code=404, detail="Aucune enseigne configurée. Utilisez POST /api/brand/setup pour commencer.")
        query = db.query(Advertiser).filter(Advertiser.is_active == True, Advertiser.id.in_(user_adv_ids))
    else:
        query = db.query(Advertiser).filter(Advertiser.is_active == True)
    if advertiser_id:
        query = query.filter(Advertiser.id == advertiser_id)
    brand = query.first()
    if not brand:
        raise HTTPException(status_code=404, detail="Aucune enseigne configurée. Utilisez POST /api/brand/setup pour commencer.")
    return brand


def _brand_to_dict(brand: Advertiser, competitors_count: int) -> dict:
    """Serialize brand to plain dict."""
    return {
        "id": brand.id,
        "company_name": brand.company_name,
        "sector": brand.sector,
        "sector_label": get_sector_label(brand.sector),
        "website": brand.website,
        "logo_url": get_logo_url(brand.website),
        "playstore_app_id": brand.playstore_app_id,
        "appstore_app_id": brand.appstore_app_id,
        "instagram_username": brand.instagram_username,
        "tiktok_username": brand.tiktok_username,
        "youtube_channel_id": brand.youtube_channel_id,
        "snapchat_entity_name": brand.snapchat_entity_name,
        "channels_configured": count_configured_channels(brand),
        "competitors_tracked": competitors_count,
        "created_at": brand.created_at.isoformat() if brand.created_at else None,
    }


def _suggestion_to_dict(comp: dict, sector: str, already_tracked: bool = False) -> dict:
    """Serialize competitor suggestion to plain dict."""
    return {
        "name": comp["name"],
        "website": comp.get("website"),
        "logo_url": get_logo_url(comp.get("website")),
        "sector": sector,
        "playstore_app_id": comp.get("playstore_app_id"),
        "appstore_app_id": comp.get("appstore_app_id"),
        "instagram_username": comp.get("instagram_username"),
        "tiktok_username": comp.get("tiktok_username"),
        "youtube_channel_id": comp.get("youtube_channel_id"),
        "already_tracked": already_tracked,
    }


def _sync_brand_competitor(db: Session, brand: Advertiser, user: User | None = None):
    """Create or update a Competitor mirror entry for the brand.

    This ensures the brand's social/app data gets fetched and appears
    in rankings alongside competitors.
    """
    # Find existing brand competitor via join table
    comp = (
        db.query(Competitor)
        .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
        .filter(
            AdvertiserCompetitor.advertiser_id == brand.id,
            AdvertiserCompetitor.is_brand == True,
            Competitor.is_active == True,
        )
        .first()
    )
    if not comp:
        # Fallback: match by name (case-insensitive, including non-brand)
        from sqlalchemy import func as sa_func
        comp = db.query(Competitor).filter(
            sa_func.lower(Competitor.name) == brand.company_name.lower(),
            Competitor.is_active == True,
        ).first()
        if comp:
            comp.is_brand = True

    if not comp:
        comp = Competitor(
            name=brand.company_name,
            website=brand.website,
            logo_url=get_logo_url(brand.website),
            playstore_app_id=brand.playstore_app_id,
            appstore_app_id=brand.appstore_app_id,
            instagram_username=brand.instagram_username,
            tiktok_username=brand.tiktok_username,
            youtube_channel_id=brand.youtube_channel_id,
            snapchat_entity_name=brand.snapchat_entity_name,
            is_brand=True,
        )
        db.add(comp)
        db.flush()

        # Create advertiser-competitor link
        db.add(AdvertiserCompetitor(advertiser_id=brand.id, competitor_id=comp.id, is_brand=True))
        db.commit()
        db.refresh(comp)

        # Trigger auto-enrichment
        import asyncio
        from routers.competitors import _auto_enrich_competitor
        asyncio.create_task(_auto_enrich_competitor(comp.id, comp))
    else:
        # Sync fields from brand to competitor
        comp.is_brand = True
        comp.website = brand.website
        comp.logo_url = get_logo_url(brand.website)
        comp.playstore_app_id = brand.playstore_app_id
        comp.appstore_app_id = brand.appstore_app_id
        comp.instagram_username = brand.instagram_username
        comp.tiktok_username = brand.tiktok_username
        comp.youtube_channel_id = brand.youtube_channel_id
        comp.snapchat_entity_name = brand.snapchat_entity_name

        # Ensure link exists
        existing_link = db.query(AdvertiserCompetitor).filter(
            AdvertiserCompetitor.advertiser_id == brand.id,
            AdvertiserCompetitor.competitor_id == comp.id,
        ).first()
        if not existing_link:
            db.add(AdvertiserCompetitor(advertiser_id=brand.id, competitor_id=comp.id, is_brand=True))

        db.commit()
        db.refresh(comp)

        # Re-enrich after field updates
        import asyncio
        from routers.competitors import _auto_enrich_competitor
        asyncio.create_task(_auto_enrich_competitor(comp.id, comp))

    return comp


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/sectors")
async def get_available_sectors():
    """Liste les secteurs d'activité disponibles."""
    return list_sectors()


@router.get("/list")
async def list_brands(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Liste toutes les enseignes de l'utilisateur."""
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    brands = db.query(Advertiser).filter(
        Advertiser.id.in_(user_adv_ids),
        Advertiser.is_active == True,
    ).order_by(Advertiser.id).all() if user_adv_ids else []
    return [
        {
            "id": b.id,
            "company_name": b.company_name,
            "sector": b.sector,
            "logo_url": get_logo_url(b.website),
        }
        for b in brands
    ]


@router.post("/setup")
async def setup_brand(
    data: BrandSetup,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Onboarding initial de l'enseigne (permet plusieurs enseignes)."""

    if data.sector not in SECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Secteur invalide. Secteurs disponibles: {list(SECTORS.keys())}"
        )

    # Check if user already has this advertiser linked
    from sqlalchemy import func as sa_func
    existing_link = (
        db.query(UserAdvertiser)
        .join(Advertiser, Advertiser.id == UserAdvertiser.advertiser_id)
        .filter(
            UserAdvertiser.user_id == user.id,
            sa_func.lower(Advertiser.company_name) == data.company_name.strip().lower(),
            Advertiser.is_active == True,
        )
        .first()
    )
    if existing_link:
        raise HTTPException(status_code=400, detail="Enseigne déjà configurée pour cet utilisateur.")

    # Check if advertiser already exists globally (another user created it)
    global_existing = db.query(Advertiser).filter(
        sa_func.lower(Advertiser.company_name) == data.company_name.strip().lower(),
        Advertiser.is_active == True,
    ).first()

    if global_existing:
        # Reuse existing advertiser, just link the new user
        brand = global_existing
        db.add(UserAdvertiser(user_id=user.id, advertiser_id=brand.id, role="member"))
        db.commit()
        db.refresh(brand)
    else:
        brand = Advertiser(
            company_name=data.company_name,
            sector=data.sector,
            website=data.website,
            logo_url=get_logo_url(data.website),
            playstore_app_id=data.playstore_app_id,
            appstore_app_id=data.appstore_app_id,
            instagram_username=data.instagram_username,
            tiktok_username=data.tiktok_username,
            youtube_channel_id=data.youtube_channel_id,
            snapchat_entity_name=data.snapchat_entity_name,
        )
        db.add(brand)
        db.flush()

        # Create user-advertiser link
        db.add(UserAdvertiser(user_id=user.id, advertiser_id=brand.id, role="owner"))
        db.commit()
        db.refresh(brand)

    # Create a mirror Competitor for the brand so its data gets enriched + auto-enrich
    _sync_brand_competitor(db, brand, user)

    suggestions = []
    for comp in get_competitors_for_sector(data.sector):
        if comp["name"].lower() == data.company_name.lower():
            continue
        suggestions.append(_suggestion_to_dict(comp, data.sector))

    competitors_count = (
        db.query(AdvertiserCompetitor)
        .join(Competitor, Competitor.id == AdvertiserCompetitor.competitor_id)
        .filter(
            AdvertiserCompetitor.advertiser_id == brand.id,
            AdvertiserCompetitor.is_brand == False,
            Competitor.is_active == True,
        )
        .count()
    )

    return JSONResponse(content={
        "brand": _brand_to_dict(brand, competitors_count),
        "suggested_competitors": suggestions,
        "message": f"Bienvenue {data.company_name}! Sélectionnez les concurrents à surveiller.",
    })


@router.get("/profile")
async def get_brand_profile(
    advertiser_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Récupère le profil de mon enseigne."""
    adv_id = advertiser_id or (int(x_advertiser_id) if x_advertiser_id else None)
    brand = get_current_brand(db, user, advertiser_id=adv_id)
    competitors_count = (
        db.query(AdvertiserCompetitor)
        .join(Competitor, Competitor.id == AdvertiserCompetitor.competitor_id)
        .filter(
            AdvertiserCompetitor.advertiser_id == brand.id,
            AdvertiserCompetitor.is_brand == False,
            Competitor.is_active == True,
        )
        .count()
    )

    return JSONResponse(content=_brand_to_dict(brand, competitors_count))


@router.delete("/reset")
async def reset_brand(
    advertiser_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Supprime l'enseigne et ses concurrents pour reconfigurer."""
    adv_id = advertiser_id or (int(x_advertiser_id) if x_advertiser_id else None)
    brand = get_current_brand(db, user, advertiser_id=adv_id)

    # Deactivate competitors linked to this advertiser
    db.query(Competitor).filter(
        Competitor.advertiser_id == brand.id,
        Competitor.is_active == True,
    ).update({"is_active": False})

    # Deactivate brand
    brand.is_active = False
    db.commit()

    return JSONResponse(content={"message": f"Enseigne '{brand.company_name}' supprimée. Vous pouvez reconfigurer."})


@router.put("/profile")
async def update_brand_profile(
    data: BrandSetup,
    advertiser_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Met à jour le profil de mon enseigne."""
    adv_id = advertiser_id or (int(x_advertiser_id) if x_advertiser_id else None)
    brand = get_current_brand(db, user, advertiser_id=adv_id)

    brand.company_name = data.company_name
    brand.sector = data.sector
    brand.website = data.website
    # Only auto-generate logo if no custom logo was uploaded
    if not brand.logo_url or not brand.logo_url.startswith("data:"):
        brand.logo_url = get_logo_url(data.website)
    brand.playstore_app_id = data.playstore_app_id
    brand.appstore_app_id = data.appstore_app_id
    brand.instagram_username = data.instagram_username
    brand.tiktok_username = data.tiktok_username
    brand.youtube_channel_id = data.youtube_channel_id
    brand.snapchat_entity_name = data.snapchat_entity_name

    db.commit()
    db.refresh(brand)

    # Sync to competitor mirror (triggers re-enrichment automatically)
    _sync_brand_competitor(db, brand, user)

    competitors_count = (
        db.query(AdvertiserCompetitor)
        .join(Competitor, Competitor.id == AdvertiserCompetitor.competitor_id)
        .filter(
            AdvertiserCompetitor.advertiser_id == brand.id,
            AdvertiserCompetitor.is_brand == False,
            Competitor.is_active == True,
        )
        .count()
    )

    return JSONResponse(content=_brand_to_dict(brand, competitors_count))


@router.post("/logo")
async def upload_brand_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Upload a custom logo (1:1 ratio, max 512KB)."""
    adv_id = int(x_advertiser_id) if x_advertiser_id else None
    brand = get_current_brand(db, user, advertiser_id=adv_id)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Le fichier doit etre une image")

    data = await file.read()
    if len(data) > 512 * 1024:
        raise HTTPException(status_code=400, detail="L'image ne doit pas depasser 512 Ko")

    b64 = base64.b64encode(data).decode("utf-8")
    brand.logo_url = f"data:{file.content_type};base64,{b64}"
    db.commit()

    return {"message": "Logo mis a jour", "logo_url": brand.logo_url}


@router.post("/sync")
async def sync_brand_competitor(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Force sync brand to competitor entry + trigger enrichment."""
    adv_id = int(x_advertiser_id) if x_advertiser_id else None
    brand = get_current_brand(db, user, advertiser_id=adv_id)
    comp = _sync_brand_competitor(db, brand, user)

    # Always trigger re-enrichment on manual sync
    import asyncio
    from routers.competitors import _auto_enrich_competitor
    asyncio.create_task(_auto_enrich_competitor(comp.id, comp))

    return JSONResponse(content={
        "message": f"Synchronisation lancée pour '{brand.company_name}'. Les données seront mises à jour en arrière-plan.",
        "competitor_id": comp.id,
    })


@router.get("/suggestions")
async def get_competitor_suggestions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Retourne les concurrents suggérés pour le secteur de l'enseigne."""
    adv_id = int(x_advertiser_id) if x_advertiser_id else None
    brand = get_current_brand(db, user, advertiser_id=adv_id)

    effective_adv_id = adv_id or brand.id
    tracked_comps = (
        db.query(Competitor)
        .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
        .filter(AdvertiserCompetitor.advertiser_id == effective_adv_id, Competitor.is_active == True)
        .all()
    )
    tracked_names = {c.name.lower() for c in tracked_comps}

    suggestions = []
    for comp in get_competitors_for_sector(brand.sector):
        if comp["name"].lower() == brand.company_name.lower():
            continue
        suggestions.append(_suggestion_to_dict(
            comp, brand.sector,
            already_tracked=comp["name"].lower() in tracked_names,
        ))

    return JSONResponse(content=suggestions)


@router.post("/suggestions/add")
async def add_suggested_competitors(
    names: List[str],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Ajoute des concurrents à partir des suggestions."""
    adv_id = int(x_advertiser_id) if x_advertiser_id else None
    brand = get_current_brand(db, user, advertiser_id=adv_id)
    sector_competitors = {c["name"].lower(): c for c in get_competitors_for_sector(brand.sector)}

    added = []
    skipped = []
    not_found = []

    for name in names:
        comp_data = sector_competitors.get(name.lower())

        if not comp_data:
            not_found.append(name)
            continue

        # Check if already linked
        existing_link = (
            db.query(AdvertiserCompetitor)
            .join(Competitor, Competitor.id == AdvertiserCompetitor.competitor_id)
            .filter(
                AdvertiserCompetitor.advertiser_id == brand.id,
                Competitor.name == comp_data["name"],
                Competitor.is_active == True,
            )
            .first()
        )
        if existing_link:
            skipped.append(name)
            continue

        # Dedup: find or create competitor
        from sqlalchemy import func as sa_func
        comp = db.query(Competitor).filter(
            sa_func.lower(Competitor.name) == comp_data["name"].lower(),
            Competitor.is_active == True,
        ).first()

        if not comp:
            comp = Competitor(
                name=comp_data["name"],
                website=comp_data.get("website"),
                logo_url=get_logo_url(comp_data.get("website")),
                playstore_app_id=comp_data.get("playstore_app_id"),
                appstore_app_id=comp_data.get("appstore_app_id"),
                instagram_username=comp_data.get("instagram_username"),
                tiktok_username=comp_data.get("tiktok_username"),
                youtube_channel_id=comp_data.get("youtube_channel_id"),
            )
            db.add(comp)
            db.flush()

        db.add(AdvertiserCompetitor(advertiser_id=brand.id, competitor_id=comp.id))
        added.append(comp_data["name"])

        import asyncio
        from routers.competitors import _auto_enrich_competitor
        asyncio.create_task(_auto_enrich_competitor(comp.id, comp))

    db.commit()

    return {
        "added": added,
        "skipped": skipped,
        "not_found": not_found,
        "total_competitors": (
            db.query(AdvertiserCompetitor)
            .join(Competitor, Competitor.id == AdvertiserCompetitor.competitor_id)
            .filter(
                AdvertiserCompetitor.advertiser_id == brand.id,
                AdvertiserCompetitor.is_brand == False,
                Competitor.is_active == True,
            )
            .count()
        ),
    }


# =============================================================================
# Social Auto-Detection
# =============================================================================

# Paths that are NOT Instagram profiles
_IG_NON_PROFILES = {
    "p", "reel", "reels", "stories", "explore", "accounts", "about",
    "legal", "developer", "direct", "tv", "lite", "ar", "shop",
}


def _is_safe_url(url: str) -> bool:
    """Block SSRF: reject internal/private IPs and metadata endpoints."""
    from urllib.parse import urlparse
    import ipaddress
    import socket

    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    # Block obvious internal hostnames
    if hostname in ("localhost", "metadata.google.internal"):
        return False
    if hostname.startswith("169.254.") or hostname.endswith(".internal"):
        return False

    try:
        ip = ipaddress.ip_address(socket.gethostbyname(hostname))
        return ip.is_global
    except (socket.gaierror, ValueError):
        return True


async def _detect_socials_from_website(website: str) -> dict:
    """Scrape a website's HTML and extract social media links."""
    import httpx

    suggestions = {}
    url = website if website.startswith("http") else f"https://{website}"

    if not _is_safe_url(url):
        return suggestions

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            })
            html = resp.text

        # Instagram
        ig_matches = re.findall(
            r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9_.]{1,30})/?',
            html
        )
        ig_filtered = [m for m in ig_matches if m.lower() not in _IG_NON_PROFILES]
        if ig_filtered:
            suggestions["instagram_username"] = ig_filtered[0]

        # TikTok
        tt_matches = re.findall(
            r'(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9_.]{1,30})/?',
            html
        )
        if tt_matches:
            suggestions["tiktok_username"] = tt_matches[0]

        # YouTube - channel ID or @handle
        yt_channel = re.findall(
            r'(?:https?://)?(?:www\.)?youtube\.com/channel/(UC[a-zA-Z0-9_-]+)',
            html
        )
        yt_handle = re.findall(
            r'(?:https?://)?(?:www\.)?youtube\.com/@([a-zA-Z0-9_-]+)',
            html
        )
        if yt_channel:
            suggestions["youtube_channel_id"] = yt_channel[0]
        elif yt_handle:
            suggestions["youtube_channel_id"] = f"@{yt_handle[0]}"

        # Play Store
        ps_matches = re.findall(
            r'play\.google\.com/store/apps/details\?id=([a-zA-Z0-9_.]+)',
            html
        )
        if ps_matches:
            suggestions["playstore_app_id"] = ps_matches[0]

        # App Store
        as_matches = re.findall(
            r'apps\.apple\.com/[a-z]{2}/app/[^/\"\']+/id(\d+)',
            html
        )
        if not as_matches:
            as_matches = re.findall(
                r'itunes\.apple\.com/[a-z]{2}/app/[^/\"\']+/id(\d+)',
                html
            )
        if as_matches:
            suggestions["appstore_app_id"] = as_matches[0]

    except Exception as e:
        logger.warning(f"Social detection failed for {website}: {e}")

    return suggestions


class SocialSuggestRequest(BaseModel):
    company_name: str
    website: Optional[str] = None


@router.post("/suggest-socials")
async def suggest_socials(data: SocialSuggestRequest, user: User = Depends(get_current_user)):
    """
    Auto-detect social media handles from the brand's website.
    1. Scrapes the website HTML for links to social profiles.
    2. Falls back to the built-in sector database if scraping yields no results.
    """
    suggestions = {}
    source = "none"

    # 1. Scrape website for social links
    if data.website:
        suggestions = await _detect_socials_from_website(data.website)
        if suggestions:
            source = "website"

    # 2. Fallback: look up company_name in sector database
    if not suggestions and data.company_name:
        name_lower = data.company_name.strip().lower()
        for sector_data in SECTORS.values():
            for comp in sector_data.get("competitors", []):
                if comp["name"].lower() == name_lower:
                    field_keys = [
                        "instagram_username", "tiktok_username", "youtube_channel_id",
                        "playstore_app_id", "appstore_app_id", "snapchat_entity_name",
                    ]
                    for key in field_keys:
                        if comp.get(key):
                            suggestions[key] = comp[key]
                    source = "sector_database"
                    break
            if suggestions:
                break

    return {
        "suggestions": suggestions,
        "detected": len(suggestions),
        "source": source,
    }

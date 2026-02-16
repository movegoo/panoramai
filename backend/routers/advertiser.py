"""
Advertiser account API router.
Endpoints for configuring advertiser profile and auto-suggesting competitors.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime

from database import get_db, Advertiser, Competitor, User
from core.auth import get_current_user
from core.sectors import (
    SECTORS as SECTORS_DB,
    get_competitors_for_sector,
    list_sectors,
    get_sector_label,
)
from models.schemas import (
    AdvertiserCreate,
    AdvertiserUpdate,
    AdvertiserResponse,
    AdvertiserOnboarding,
    CompetitorSuggestion,
)

router = APIRouter()


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/sectors")
async def get_available_sectors():
    """Get list of available business sectors."""
    return {
        "sectors": list_sectors(),
        "description": "Select your business sector to get relevant competitor suggestions"
    }


@router.post("/onboard")
async def onboard_advertiser(
    data: AdvertiserOnboarding,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Complete advertiser onboarding.

    Creates advertiser profile and automatically adds suggested competitors.
    """
    # Check if advertiser already exists for this user
    existing = db.query(Advertiser).filter(
        Advertiser.company_name == data.company_name,
        Advertiser.user_id == user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Advertiser already exists")

    # Create advertiser
    advertiser = Advertiser(
        company_name=data.company_name,
        sector=data.sector,
        website=data.website,
        playstore_app_id=data.playstore_app_id,
        appstore_app_id=data.appstore_app_id,
        instagram_username=data.instagram_username,
        tiktok_username=data.tiktok_username,
        youtube_channel_id=data.youtube_channel_id,
        contact_email=data.contact_email,
        user_id=user.id,
    )
    db.add(advertiser)
    db.commit()
    db.refresh(advertiser)

    # Auto-add selected competitors
    if data.selected_competitors:
        for comp_name in data.selected_competitors:
            await _add_competitor_by_name(db, comp_name, data.sector, user_id=user.id, advertiser_id=advertiser.id)

    return advertiser


@router.get("/suggestions/{sector}")
async def get_competitor_suggestions(
    sector: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[CompetitorSuggestion]:
    """
    Get competitor suggestions for a given sector.

    Returns a list of known competitors in the sector with their
    social media and app store information.
    """
    sector_competitors = get_competitors_for_sector(sector)
    if not sector_competitors:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown sector. Available: {list(SECTORS_DB.keys())}"
        )

    suggestions = []
    existing_query = db.query(Competitor).filter(Competitor.is_active == True)
    if user:
        existing_query = existing_query.filter(Competitor.user_id == user.id)
    existing_names = {c.name.lower() for c in existing_query.all()}

    for comp in sector_competitors:
        already = comp["name"].lower() in existing_names

        suggestions.append(CompetitorSuggestion(
            name=comp["name"],
            website=comp.get("website"),
            sector=sector,
            playstore_app_id=comp.get("playstore_app_id"),
            appstore_app_id=comp.get("appstore_app_id"),
            instagram_username=comp.get("instagram_username"),
            tiktok_username=comp.get("tiktok_username"),
            youtube_channel_id=comp.get("youtube_channel_id"),
            already_tracked=already,
        ))

    return suggestions


@router.post("/suggestions/{sector}/add-all")
async def add_all_suggested_competitors(
    sector: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add all suggested competitors for a sector."""
    sector_competitors = get_competitors_for_sector(sector)
    if not sector_competitors:
        raise HTTPException(status_code=400, detail=f"Unknown sector")

    # Get user's advertiser
    advertiser = db.query(Advertiser).filter(
        Advertiser.user_id == user.id, Advertiser.is_active == True
    ).first()

    added = []
    skipped = []

    for comp in sector_competitors:
        existing = db.query(Competitor).filter(
            Competitor.name == comp["name"],
            Competitor.user_id == user.id,
            Competitor.is_active == True
        ).first()

        if existing:
            skipped.append(comp["name"])
            continue

        new_competitor = Competitor(
            name=comp["name"],
            website=comp.get("website"),
            playstore_app_id=comp.get("playstore_app_id"),
            appstore_app_id=comp.get("appstore_app_id"),
            instagram_username=comp.get("instagram_username"),
            tiktok_username=comp.get("tiktok_username"),
            youtube_channel_id=comp.get("youtube_channel_id"),
            user_id=user.id,
            advertiser_id=advertiser.id if advertiser else None,
        )
        db.add(new_competitor)
        added.append(comp["name"])

    db.commit()

    return {
        "message": f"Added {len(added)} competitors",
        "added": added,
        "skipped": skipped,
        "sector": sector
    }


@router.post("/suggestions/add")
async def add_selected_competitors(
    competitor_names: List[str],
    sector: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add selected competitors from suggestions."""
    sector_comps = get_competitors_for_sector(sector)
    if not sector_comps:
        raise HTTPException(status_code=400, detail=f"Unknown sector")

    # Get user's advertiser
    advertiser = db.query(Advertiser).filter(
        Advertiser.user_id == user.id, Advertiser.is_active == True
    ).first()

    added = []
    not_found = []
    skipped = []

    sector_competitors = {c["name"].lower(): c for c in sector_comps}

    for name in competitor_names:
        comp_data = sector_competitors.get(name.lower())

        if not comp_data:
            not_found.append(name)
            continue

        existing = db.query(Competitor).filter(
            Competitor.name == comp_data["name"],
            Competitor.user_id == user.id,
            Competitor.is_active == True
        ).first()

        if existing:
            skipped.append(name)
            continue

        new_competitor = Competitor(
            name=comp_data["name"],
            website=comp_data.get("website"),
            playstore_app_id=comp_data.get("playstore_app_id"),
            appstore_app_id=comp_data.get("appstore_app_id"),
            instagram_username=comp_data.get("instagram_username"),
            tiktok_username=comp_data.get("tiktok_username"),
            youtube_channel_id=comp_data.get("youtube_channel_id"),
            user_id=user.id,
            advertiser_id=advertiser.id if advertiser else None,
        )
        db.add(new_competitor)
        added.append(comp_data["name"])

    db.commit()

    return {
        "message": f"Added {len(added)} competitors",
        "added": added,
        "skipped": skipped,
        "not_found": not_found
    }


@router.get("/")
async def list_advertisers(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """List all advertisers."""
    query = db.query(Advertiser).filter(Advertiser.is_active == True)
    if user:
        query = query.filter(Advertiser.user_id == user.id)
    return query.all()


@router.get("/{advertiser_id}")
async def get_advertiser(
    advertiser_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get advertiser by ID."""
    advertiser = db.query(Advertiser).filter(
        Advertiser.id == advertiser_id,
        Advertiser.user_id == user.id,
    ).first()
    if not advertiser:
        raise HTTPException(status_code=404, detail="Advertiser not found")
    return advertiser


@router.put("/{advertiser_id}")
async def update_advertiser(
    advertiser_id: int,
    update: AdvertiserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update advertiser profile."""
    advertiser = db.query(Advertiser).filter(
        Advertiser.id == advertiser_id,
        Advertiser.user_id == user.id,
    ).first()
    if not advertiser:
        raise HTTPException(status_code=404, detail="Advertiser not found")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(advertiser, field, value)

    db.commit()
    db.refresh(advertiser)
    return advertiser


@router.delete("/{advertiser_id}")
async def delete_advertiser(
    advertiser_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Soft delete an advertiser."""
    advertiser = db.query(Advertiser).filter(
        Advertiser.id == advertiser_id,
        Advertiser.user_id == user.id,
    ).first()
    if not advertiser:
        raise HTTPException(status_code=404, detail="Advertiser not found")

    advertiser.is_active = False
    db.commit()
    return {"message": "Advertiser deactivated"}


@router.post("/patch-social-handles")
async def patch_social_handles(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Patch existing competitors with missing social handles from the sector database."""
    # Build a lookup: lowercase name -> best data from all sectors
    known = {}
    for sector_data in SECTORS_DB.values():
        for comp in sector_data.get("competitors", []):
            known[comp["name"].lower()] = comp

    competitors = db.query(Competitor).filter(
        Competitor.user_id == user.id, Competitor.is_active == True
    ).all()

    patched = []
    for comp in competitors:
        ref = known.get(comp.name.lower())
        if not ref:
            continue

        updated_fields = []
        for field in ["tiktok_username", "instagram_username", "youtube_channel_id",
                      "playstore_app_id", "appstore_app_id"]:
            current = getattr(comp, field, None)
            new_val = ref.get(field)
            if new_val and (not current or current != new_val):
                setattr(comp, field, new_val)
                updated_fields.append(field)

        if updated_fields:
            patched.append({"name": comp.name, "updated": updated_fields})

    if patched:
        db.commit()

    return {
        "message": f"Patched {len(patched)} competitors",
        "patched": patched,
        "total_checked": len(competitors),
    }


# =============================================================================
# Helpers
# =============================================================================

async def _add_competitor_by_name(db: Session, name: str, sector: str, user_id: int = None, advertiser_id: int = None):
    """Add a competitor by name from the sector database."""
    sector_competitors = get_competitors_for_sector(sector)
    if not sector_competitors:
        return None

    for comp in sector_competitors:
        if comp["name"].lower() == name.lower():
            query = db.query(Competitor).filter(
                Competitor.name == comp["name"],
                Competitor.is_active == True,
            )
            if user_id:
                query = query.filter(Competitor.user_id == user_id)
            existing = query.first()

            if existing:
                return existing

            new_competitor = Competitor(
                name=comp["name"],
                website=comp.get("website"),
                playstore_app_id=comp.get("playstore_app_id"),
                appstore_app_id=comp.get("appstore_app_id"),
                instagram_username=comp.get("instagram_username"),
                tiktok_username=comp.get("tiktok_username"),
                youtube_channel_id=comp.get("youtube_channel_id"),
                user_id=user_id,
                advertiser_id=advertiser_id,
            )
            db.add(new_competitor)
            db.commit()
            db.refresh(new_competitor)
            return new_competitor

    return None

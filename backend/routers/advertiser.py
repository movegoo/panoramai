"""
Advertiser account API router.
Endpoints for configuring advertiser profile and auto-suggesting competitors.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime

from database import get_db, Advertiser, Competitor, User, AdvertiserCompetitor, UserAdvertiser
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
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    if user_adv_ids:
        existing = db.query(Advertiser).filter(
            Advertiser.company_name == data.company_name,
            Advertiser.id.in_(user_adv_ids),
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
    )
    db.add(advertiser)
    db.flush()

    # Create user-advertiser link
    db.add(UserAdvertiser(user_id=user.id, advertiser_id=advertiser.id, role="owner"))
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
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    if user_adv_ids:
        existing_comps = (
            db.query(Competitor)
            .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
            .filter(AdvertiserCompetitor.advertiser_id.in_(user_adv_ids), Competitor.is_active == True)
            .all()
        )
        existing_names = {c.name.lower() for c in existing_comps}
    else:
        existing_names = set()

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

    # Get user's first advertiser
    user_adv = db.query(UserAdvertiser).filter(UserAdvertiser.user_id == user.id).first()
    advertiser_id = user_adv.advertiser_id if user_adv else None

    added = []
    skipped = []

    for comp in sector_competitors:
        from sqlalchemy import func as sa_func
        # Check if already linked to any user advertiser
        existing_link = None
        if advertiser_id:
            existing_link = (
                db.query(AdvertiserCompetitor)
                .join(Competitor, Competitor.id == AdvertiserCompetitor.competitor_id)
                .filter(
                    AdvertiserCompetitor.advertiser_id == advertiser_id,
                    sa_func.lower(Competitor.name) == comp["name"].lower(),
                    Competitor.is_active == True,
                )
                .first()
            )

        if existing_link:
            skipped.append(comp["name"])
            continue

        # Dedup: find or create
        existing_comp = db.query(Competitor).filter(
            sa_func.lower(Competitor.name) == comp["name"].lower(),
            Competitor.is_active == True,
        ).first()

        if not existing_comp:
            existing_comp = Competitor(
                name=comp["name"],
                website=comp.get("website"),
                playstore_app_id=comp.get("playstore_app_id"),
                appstore_app_id=comp.get("appstore_app_id"),
                instagram_username=comp.get("instagram_username"),
                tiktok_username=comp.get("tiktok_username"),
                youtube_channel_id=comp.get("youtube_channel_id"),
            )
            db.add(existing_comp)
            db.flush()

        if advertiser_id:
            db.add(AdvertiserCompetitor(advertiser_id=advertiser_id, competitor_id=existing_comp.id))
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

    # Get user's first advertiser
    user_adv = db.query(UserAdvertiser).filter(UserAdvertiser.user_id == user.id).first()
    advertiser_id = user_adv.advertiser_id if user_adv else None

    added = []
    not_found = []
    skipped = []

    sector_competitors = {c["name"].lower(): c for c in sector_comps}

    for name in competitor_names:
        comp_data = sector_competitors.get(name.lower())

        if not comp_data:
            not_found.append(name)
            continue

        from sqlalchemy import func as sa_func
        # Check if already linked
        if advertiser_id:
            existing_link = (
                db.query(AdvertiserCompetitor)
                .join(Competitor, Competitor.id == AdvertiserCompetitor.competitor_id)
                .filter(
                    AdvertiserCompetitor.advertiser_id == advertiser_id,
                    sa_func.lower(Competitor.name) == comp_data["name"].lower(),
                    Competitor.is_active == True,
                )
                .first()
            )
            if existing_link:
                skipped.append(name)
                continue

        # Dedup: find or create
        existing_comp = db.query(Competitor).filter(
            sa_func.lower(Competitor.name) == comp_data["name"].lower(),
            Competitor.is_active == True,
        ).first()

        if not existing_comp:
            existing_comp = Competitor(
                name=comp_data["name"],
                website=comp_data.get("website"),
                playstore_app_id=comp_data.get("playstore_app_id"),
                appstore_app_id=comp_data.get("appstore_app_id"),
                instagram_username=comp_data.get("instagram_username"),
                tiktok_username=comp_data.get("tiktok_username"),
                youtube_channel_id=comp_data.get("youtube_channel_id"),
            )
            db.add(existing_comp)
            db.flush()

        if advertiser_id:
            db.add(AdvertiserCompetitor(advertiser_id=advertiser_id, competitor_id=existing_comp.id))
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
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    if not user_adv_ids:
        return []
    return db.query(Advertiser).filter(Advertiser.id.in_(user_adv_ids), Advertiser.is_active == True).all()


@router.get("/{advertiser_id}")
async def get_advertiser(
    advertiser_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get advertiser by ID."""
    link = db.query(UserAdvertiser).filter(
        UserAdvertiser.user_id == user.id, UserAdvertiser.advertiser_id == advertiser_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Advertiser not found")
    advertiser = db.query(Advertiser).filter(Advertiser.id == advertiser_id).first()
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
    link = db.query(UserAdvertiser).filter(
        UserAdvertiser.user_id == user.id, UserAdvertiser.advertiser_id == advertiser_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Advertiser not found")
    advertiser = db.query(Advertiser).filter(Advertiser.id == advertiser_id).first()
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
    link = db.query(UserAdvertiser).filter(
        UserAdvertiser.user_id == user.id, UserAdvertiser.advertiser_id == advertiser_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Advertiser not found")
    advertiser = db.query(Advertiser).filter(Advertiser.id == advertiser_id).first()
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

    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    if not user_adv_ids:
        return {"message": "Patched 0 competitors", "patched": [], "total_checked": 0}
    competitors = (
        db.query(Competitor)
        .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
        .filter(AdvertiserCompetitor.advertiser_id.in_(user_adv_ids), Competitor.is_active == True)
        .all()
    )

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
    """Add a competitor by name from the sector database (with deduplication)."""
    sector_competitors = get_competitors_for_sector(sector)
    if not sector_competitors:
        return None

    from sqlalchemy import func as sa_func
    for comp in sector_competitors:
        if comp["name"].lower() == name.lower():
            # Dedup: find existing
            existing = db.query(Competitor).filter(
                sa_func.lower(Competitor.name) == comp["name"].lower(),
                Competitor.is_active == True,
            ).first()

            if not existing:
                existing = Competitor(
                    name=comp["name"],
                    website=comp.get("website"),
                    playstore_app_id=comp.get("playstore_app_id"),
                    appstore_app_id=comp.get("appstore_app_id"),
                    instagram_username=comp.get("instagram_username"),
                    tiktok_username=comp.get("tiktok_username"),
                    youtube_channel_id=comp.get("youtube_channel_id"),
                )
                db.add(existing)
                db.flush()

            # Create advertiser link if needed
            if advertiser_id:
                link = db.query(AdvertiserCompetitor).filter(
                    AdvertiserCompetitor.advertiser_id == advertiser_id,
                    AdvertiserCompetitor.competitor_id == existing.id,
                ).first()
                if not link:
                    db.add(AdvertiserCompetitor(advertiser_id=advertiser_id, competitor_id=existing.id))

            db.commit()
            db.refresh(existing)
            return existing

    return None


# =============================================================================
# MIGRATION: Link orphan advertisers to their creators
# =============================================================================

@router.post("/migrate-links")
def migrate_advertiser_links(
    db: Session = Depends(get_db),
):
    """One-time migration: for every advertiser with a user_id, ensure a
    user_advertisers link exists. Fixes legacy data created before the
    many-to-many join table was introduced.

    No auth required (temporary migration endpoint — remove after use).
    """
    # Find all advertisers that have a user_id set
    advertisers = db.query(Advertiser).filter(
        Advertiser.user_id.isnot(None),
        Advertiser.is_active == True,
    ).all()

    created = []
    skipped = []

    for adv in advertisers:
        # Check if link already exists
        existing = db.query(UserAdvertiser).filter(
            UserAdvertiser.user_id == adv.user_id,
            UserAdvertiser.advertiser_id == adv.id,
        ).first()

        if existing:
            skipped.append({"advertiser_id": adv.id, "name": adv.company_name, "user_id": adv.user_id})
        else:
            db.add(UserAdvertiser(
                user_id=adv.user_id,
                advertiser_id=adv.id,
                role="owner",
            ))
            created.append({"advertiser_id": adv.id, "name": adv.company_name, "user_id": adv.user_id})

    db.commit()

    return {
        "created_links": len(created),
        "skipped_existing": len(skipped),
        "created": created,
        "skipped": skipped,
    }

"""
Mon Enseigne - Brand management router.
Central entity representing the user's retail brand.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db, Advertiser, Competitor
from models.schemas import BrandSetup, BrandProfile, SetupResponse, CompetitorSuggestion, Sector
from core.sectors import get_sector_label, get_competitors_for_sector, list_sectors, SECTORS

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


def get_current_brand(db: Session) -> Advertiser:
    """Récupère l'enseigne courante (single-tenant pour l'instant)."""
    brand = db.query(Advertiser).filter(Advertiser.is_active == True).first()
    if not brand:
        raise HTTPException(
            status_code=404,
            detail="Aucune enseigne configurée. Utilisez POST /api/brand/setup pour commencer."
        )
    return brand


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/sectors", response_model=List[Sector])
async def get_available_sectors():
    """Liste les secteurs d'activité disponibles."""
    return list_sectors()


@router.post("/setup", response_model=SetupResponse)
async def setup_brand(data: BrandSetup, db: Session = Depends(get_db)):
    """
    Onboarding initial de l'enseigne.

    Crée le profil de l'enseigne et retourne les concurrents suggérés
    pour le secteur choisi.
    """
    # Vérifie si une enseigne existe déjà
    existing = db.query(Advertiser).filter(Advertiser.is_active == True).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Une enseigne est déjà configurée: {existing.company_name}"
        )

    # Valide le secteur
    if data.sector not in SECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Secteur invalide. Secteurs disponibles: {list(SECTORS.keys())}"
        )

    # Crée l'enseigne
    brand = Advertiser(
        company_name=data.company_name,
        sector=data.sector,
        website=data.website,
        playstore_app_id=data.playstore_app_id,
        appstore_app_id=data.appstore_app_id,
        instagram_username=data.instagram_username,
        tiktok_username=data.tiktok_username,
        youtube_channel_id=data.youtube_channel_id,
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)

    # Récupère les concurrents suggérés
    suggestions = []
    for comp in get_competitors_for_sector(data.sector):
        # Ne pas suggérer l'enseigne elle-même
        if comp["name"].lower() == data.company_name.lower():
            continue
        suggestions.append(CompetitorSuggestion(
            name=comp["name"],
            website=comp.get("website"),
            sector=data.sector,
            playstore_app_id=comp.get("playstore_app_id"),
            appstore_app_id=comp.get("appstore_app_id"),
            instagram_username=comp.get("instagram_username"),
            tiktok_username=comp.get("tiktok_username"),
            youtube_channel_id=comp.get("youtube_channel_id"),
            already_tracked=False,
        ))

    competitors_count = db.query(Competitor).filter(Competitor.is_active == True).count()

    profile = BrandProfile(
        id=brand.id,
        company_name=brand.company_name,
        sector=brand.sector,
        sector_label=get_sector_label(brand.sector),
        website=brand.website,
        playstore_app_id=brand.playstore_app_id,
        appstore_app_id=brand.appstore_app_id,
        instagram_username=brand.instagram_username,
        tiktok_username=brand.tiktok_username,
        youtube_channel_id=brand.youtube_channel_id,
        channels_configured=count_configured_channels(brand),
        competitors_tracked=competitors_count,
        created_at=brand.created_at,
    )

    return SetupResponse(
        brand=profile,
        suggested_competitors=suggestions,
        message=f"Bienvenue {data.company_name}! Sélectionnez les concurrents à surveiller."
    )


@router.get("/profile", response_model=BrandProfile)
async def get_brand_profile(db: Session = Depends(get_db)):
    """Récupère le profil de mon enseigne."""
    brand = get_current_brand(db)
    competitors_count = db.query(Competitor).filter(Competitor.is_active == True).count()

    return BrandProfile(
        id=brand.id,
        company_name=brand.company_name,
        sector=brand.sector,
        sector_label=get_sector_label(brand.sector),
        website=brand.website,
        playstore_app_id=brand.playstore_app_id,
        appstore_app_id=brand.appstore_app_id,
        instagram_username=brand.instagram_username,
        tiktok_username=brand.tiktok_username,
        youtube_channel_id=brand.youtube_channel_id,
        channels_configured=count_configured_channels(brand),
        competitors_tracked=competitors_count,
        created_at=brand.created_at,
    )


@router.put("/profile", response_model=BrandProfile)
async def update_brand_profile(data: BrandSetup, db: Session = Depends(get_db)):
    """Met à jour le profil de mon enseigne."""
    brand = get_current_brand(db)

    brand.company_name = data.company_name
    brand.sector = data.sector
    brand.website = data.website
    brand.playstore_app_id = data.playstore_app_id
    brand.appstore_app_id = data.appstore_app_id
    brand.instagram_username = data.instagram_username
    brand.tiktok_username = data.tiktok_username
    brand.youtube_channel_id = data.youtube_channel_id

    db.commit()
    db.refresh(brand)

    competitors_count = db.query(Competitor).filter(Competitor.is_active == True).count()

    return BrandProfile(
        id=brand.id,
        company_name=brand.company_name,
        sector=brand.sector,
        sector_label=get_sector_label(brand.sector),
        website=brand.website,
        playstore_app_id=brand.playstore_app_id,
        appstore_app_id=brand.appstore_app_id,
        instagram_username=brand.instagram_username,
        tiktok_username=brand.tiktok_username,
        youtube_channel_id=brand.youtube_channel_id,
        channels_configured=count_configured_channels(brand),
        competitors_tracked=competitors_count,
        created_at=brand.created_at,
    )


@router.get("/suggestions", response_model=List[CompetitorSuggestion])
async def get_competitor_suggestions(db: Session = Depends(get_db)):
    """
    Retourne les concurrents suggérés pour le secteur de l'enseigne.
    Indique lesquels sont déjà suivis.
    """
    brand = get_current_brand(db)

    # Concurrents déjà suivis
    tracked_names = {
        c.name.lower()
        for c in db.query(Competitor).filter(Competitor.is_active == True).all()
    }

    suggestions = []
    for comp in get_competitors_for_sector(brand.sector):
        # Ne pas suggérer l'enseigne elle-même
        if comp["name"].lower() == brand.company_name.lower():
            continue

        suggestions.append(CompetitorSuggestion(
            name=comp["name"],
            website=comp.get("website"),
            sector=brand.sector,
            playstore_app_id=comp.get("playstore_app_id"),
            appstore_app_id=comp.get("appstore_app_id"),
            instagram_username=comp.get("instagram_username"),
            tiktok_username=comp.get("tiktok_username"),
            youtube_channel_id=comp.get("youtube_channel_id"),
            already_tracked=comp["name"].lower() in tracked_names,
        ))

    return suggestions


@router.post("/suggestions/add")
async def add_suggested_competitors(
    names: List[str],
    db: Session = Depends(get_db)
):
    """Ajoute des concurrents à partir des suggestions."""
    brand = get_current_brand(db)
    sector_competitors = {c["name"].lower(): c for c in get_competitors_for_sector(brand.sector)}

    added = []
    skipped = []
    not_found = []

    for name in names:
        comp_data = sector_competitors.get(name.lower())

        if not comp_data:
            not_found.append(name)
            continue

        # Vérifie si déjà existant
        existing = db.query(Competitor).filter(
            Competitor.name == comp_data["name"],
            Competitor.is_active == True
        ).first()

        if existing:
            skipped.append(name)
            continue

        # Ajoute le concurrent
        new_competitor = Competitor(
            name=comp_data["name"],
            website=comp_data.get("website"),
            playstore_app_id=comp_data.get("playstore_app_id"),
            appstore_app_id=comp_data.get("appstore_app_id"),
            instagram_username=comp_data.get("instagram_username"),
            tiktok_username=comp_data.get("tiktok_username"),
            youtube_channel_id=comp_data.get("youtube_channel_id"),
        )
        db.add(new_competitor)
        db.flush()  # Get ID before background task
        added.append(comp_data["name"])

        # Auto-fetch all data in background
        import asyncio
        from routers.competitors import _auto_enrich_competitor
        asyncio.create_task(_auto_enrich_competitor(new_competitor.id, new_competitor))

    db.commit()

    return {
        "added": added,
        "skipped": skipped,
        "not_found": not_found,
        "total_competitors": db.query(Competitor).filter(Competitor.is_active == True).count()
    }

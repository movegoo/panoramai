"""
Mon Enseigne - Brand management router.
Central entity representing the user's retail brand.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List

from database import get_db, Advertiser, Competitor, User
from models.schemas import BrandSetup
from core.sectors import get_sector_label, get_competitors_for_sector, list_sectors, SECTORS
from core.auth import get_current_user, get_optional_user

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


def get_current_brand(db: Session, user: User | None = None) -> Advertiser:
    """Récupère l'enseigne courante, filtrée par user si authentifié."""
    query = db.query(Advertiser).filter(Advertiser.is_active == True)
    if user:
        query = query.filter(Advertiser.user_id == user.id)
    brand = query.first()
    if not brand:
        raise HTTPException(
            status_code=404,
            detail="Aucune enseigne configurée. Utilisez POST /api/brand/setup pour commencer."
        )
    return brand


def _brand_to_dict(brand: Advertiser, competitors_count: int) -> dict:
    """Serialize brand to plain dict."""
    return {
        "id": brand.id,
        "company_name": brand.company_name,
        "sector": brand.sector,
        "sector_label": get_sector_label(brand.sector),
        "website": brand.website,
        "playstore_app_id": brand.playstore_app_id,
        "appstore_app_id": brand.appstore_app_id,
        "instagram_username": brand.instagram_username,
        "tiktok_username": brand.tiktok_username,
        "youtube_channel_id": brand.youtube_channel_id,
        "channels_configured": count_configured_channels(brand),
        "competitors_tracked": competitors_count,
        "created_at": brand.created_at.isoformat() if brand.created_at else None,
    }


def _suggestion_to_dict(comp: dict, sector: str, already_tracked: bool = False) -> dict:
    """Serialize competitor suggestion to plain dict."""
    return {
        "name": comp["name"],
        "website": comp.get("website"),
        "sector": sector,
        "playstore_app_id": comp.get("playstore_app_id"),
        "appstore_app_id": comp.get("appstore_app_id"),
        "instagram_username": comp.get("instagram_username"),
        "tiktok_username": comp.get("tiktok_username"),
        "youtube_channel_id": comp.get("youtube_channel_id"),
        "already_tracked": already_tracked,
    }


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/sectors")
async def get_available_sectors():
    """Liste les secteurs d'activité disponibles."""
    return list_sectors()


@router.post("/setup")
async def setup_brand(
    data: BrandSetup,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Onboarding initial de l'enseigne."""
    exist_query = db.query(Advertiser).filter(Advertiser.is_active == True)
    if user:
        exist_query = exist_query.filter(Advertiser.user_id == user.id)
    existing = exist_query.first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Une enseigne est déjà configurée: {existing.company_name}"
        )

    if data.sector not in SECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Secteur invalide. Secteurs disponibles: {list(SECTORS.keys())}"
        )

    brand = Advertiser(
        user_id=user.id if user else None,
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

    suggestions = []
    for comp in get_competitors_for_sector(data.sector):
        if comp["name"].lower() == data.company_name.lower():
            continue
        suggestions.append(_suggestion_to_dict(comp, data.sector))

    competitors_count = db.query(Competitor).filter(
        Competitor.is_active == True,
        *([Competitor.user_id == user.id] if user else []),
    ).count()

    return JSONResponse(content={
        "brand": _brand_to_dict(brand, competitors_count),
        "suggested_competitors": suggestions,
        "message": f"Bienvenue {data.company_name}! Sélectionnez les concurrents à surveiller.",
    })


@router.get("/profile")
async def get_brand_profile(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Récupère le profil de mon enseigne."""
    brand = get_current_brand(db, user)
    competitors_count = db.query(Competitor).filter(
        Competitor.is_active == True,
        *([Competitor.user_id == user.id] if user else []),
    ).count()

    return JSONResponse(content=_brand_to_dict(brand, competitors_count))


@router.delete("/reset")
async def reset_brand(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Supprime l'enseigne et ses concurrents pour reconfigurer."""
    query = db.query(Advertiser).filter(Advertiser.is_active == True)
    if user:
        query = query.filter(Advertiser.user_id == user.id)
    brand = query.first()
    if not brand:
        raise HTTPException(status_code=404, detail="Aucune enseigne configurée")

    # Deactivate competitors
    comp_query = db.query(Competitor).filter(Competitor.is_active == True)
    if user:
        comp_query = comp_query.filter(Competitor.user_id == user.id)
    comp_query.update({"is_active": False})

    # Deactivate brand
    brand.is_active = False
    db.commit()

    return JSONResponse(content={"message": f"Enseigne '{brand.company_name}' supprimée. Vous pouvez reconfigurer."})


@router.put("/profile")
async def update_brand_profile(
    data: BrandSetup,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Met à jour le profil de mon enseigne."""
    brand = get_current_brand(db, user)

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

    competitors_count = db.query(Competitor).filter(
        Competitor.is_active == True,
        *([Competitor.user_id == user.id] if user else []),
    ).count()

    return JSONResponse(content=_brand_to_dict(brand, competitors_count))


@router.get("/suggestions")
async def get_competitor_suggestions(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Retourne les concurrents suggérés pour le secteur de l'enseigne."""
    brand = get_current_brand(db, user)

    comp_query = db.query(Competitor).filter(Competitor.is_active == True)
    if user:
        comp_query = comp_query.filter(Competitor.user_id == user.id)
    tracked_names = {c.name.lower() for c in comp_query.all()}

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
    user: User | None = Depends(get_optional_user),
):
    """Ajoute des concurrents à partir des suggestions."""
    brand = get_current_brand(db, user)
    sector_competitors = {c["name"].lower(): c for c in get_competitors_for_sector(brand.sector)}

    added = []
    skipped = []
    not_found = []

    for name in names:
        comp_data = sector_competitors.get(name.lower())

        if not comp_data:
            not_found.append(name)
            continue

        exist_query = db.query(Competitor).filter(
            Competitor.name == comp_data["name"],
            Competitor.is_active == True,
        )
        if user:
            exist_query = exist_query.filter(Competitor.user_id == user.id)
        if exist_query.first():
            skipped.append(name)
            continue

        new_competitor = Competitor(
            user_id=(user.id if user else None),
            name=comp_data["name"],
            website=comp_data.get("website"),
            playstore_app_id=comp_data.get("playstore_app_id"),
            appstore_app_id=comp_data.get("appstore_app_id"),
            instagram_username=comp_data.get("instagram_username"),
            tiktok_username=comp_data.get("tiktok_username"),
            youtube_channel_id=comp_data.get("youtube_channel_id"),
        )
        db.add(new_competitor)
        db.flush()
        added.append(comp_data["name"])

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

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
from models.schemas import (
    AdvertiserCreate,
    AdvertiserUpdate,
    AdvertiserResponse,
    AdvertiserOnboarding,
    CompetitorSuggestion,
)

router = APIRouter()


# =============================================================================
# Competitor Database by Sector
# =============================================================================

COMPETITORS_BY_SECTOR = {
    "supermarche": [
        {
            "name": "Carrefour",
            "website": "https://www.carrefour.fr",
            "playstore_app_id": "com.carrefour.it.moncarrefour",
            "appstore_app_id": "378498296",
            "instagram_username": "carrefourfrance",
            "tiktok_username": "carrefourfrance",
            "youtube_channel_id": "UCfhwXXWV0MT9hbXR3SJMXjQ",
        },
        {
            "name": "Leclerc",
            "website": "https://www.e.leclerc",
            "playstore_app_id": "com.eleclerc",
            "appstore_app_id": "1193842898",
            "instagram_username": "e.leclerc",
            "tiktok_username": "e.leclerc",
            "youtube_channel_id": "UCrnLMg8vyroKjPQS-IX7Opg",
        },
        {
            "name": "Auchan",
            "website": "https://www.auchan.fr",
            "playstore_app_id": "com.auchan.android",
            "appstore_app_id": "541227977",
            "instagram_username": "auchan_france",
            "tiktok_username": "auchan",
            "youtube_channel_id": "AuchanFrance",
        },
        {
            "name": "Intermarché",
            "website": "https://www.intermarche.com",
            "playstore_app_id": "com.intermarche.mobile",
            "appstore_app_id": "1447048498",
            "instagram_username": "intermarche",
            "tiktok_username": "intermarche",
            "youtube_channel_id": "intermarche",
        },
        {
            "name": "Lidl",
            "website": "https://www.lidl.fr",
            "playstore_app_id": "de.lidl.lidlplus.lidlplus",
            "appstore_app_id": "1276382498",
            "instagram_username": "lidlfrance",
            "tiktok_username": "lidlfrance",
            "youtube_channel_id": "lidlfrance",
        },
        {
            "name": "Monoprix",
            "website": "https://www.monoprix.fr",
            "playstore_app_id": "com.monoprix.app",
            "appstore_app_id": "966459890",
            "instagram_username": "monoprix",
            "tiktok_username": "monoprix",
        },
        {
            "name": "Casino",
            "website": "https://www.casino.fr",
            "playstore_app_id": "fr.casino.fidelite",
            "appstore_app_id": "1273195340",
            "instagram_username": "supermarchescasino",
            "tiktok_username": "casino_france",
            "youtube_channel_id": "UCf9Q100FQEx5cPSF9VWOuLQ",
        },
        {
            "name": "Franprix",
            "website": "https://www.franprix.fr",
            "playstore_app_id": "com.franprix.catalogue",
            "appstore_app_id": "1250331401",
            "instagram_username": "franprix_officiel",
            "tiktok_username": "franprix_fr",
        },
    ],
    "mode": [
        {
            "name": "Zara",
            "website": "https://www.zara.com/fr",
            "playstore_app_id": "com.inditex.zara",
            "appstore_app_id": "547347221",
            "instagram_username": "zara",
            "tiktok_username": "zara",
            "youtube_channel_id": "zara",
        },
        {
            "name": "H&M",
            "website": "https://www.hm.com/fr",
            "playstore_app_id": "com.hm.goe",
            "appstore_app_id": "834465911",
            "instagram_username": "hm",
            "tiktok_username": "hm",
            "youtube_channel_id": "UCoc8tpGCY1wrp8pV7mI0scA",
        },
        {
            "name": "Kiabi",
            "website": "https://www.kiabi.com",
            "playstore_app_id": "com.kiabi.app",
            "appstore_app_id": "495571498",
            "instagram_username": "kiabi_official",
            "tiktok_username": "kiabi_official",
            "youtube_channel_id": "kiabi",
        },
        {
            "name": "Celio",
            "website": "https://www.celio.com",
            "playstore_app_id": "com.celio.app",
            "instagram_username": "celio_official",
            "tiktok_username": "celio_official",
        },
        {
            "name": "Jules",
            "website": "https://www.jules.com",
            "playstore_app_id": "com.jules.app",
            "instagram_username": "jules_officiel",
            "tiktok_username": "jules_officiel",
        },
    ],
    "beaute": [
        {
            "name": "Sephora",
            "website": "https://www.sephora.fr",
            "playstore_app_id": "com.sephora.android",
            "appstore_app_id": "393328150",
            "instagram_username": "sephorafrance",
            "tiktok_username": "sephorafrance",
            "youtube_channel_id": "sephorafrance",
        },
        {
            "name": "Nocibé",
            "website": "https://www.nocibe.fr",
            "playstore_app_id": "com.douglas.nocibe",
            "appstore_app_id": "1123649654",
            "instagram_username": "nocibe_france",
            "tiktok_username": "nocibe_france",
        },
        {
            "name": "Marionnaud",
            "website": "https://www.marionnaud.fr",
            "playstore_app_id": "com.marionnaud.android",
            "appstore_app_id": "1127368763",
            "instagram_username": "marionnaud_france",
            "tiktok_username": "marionnaudfrance",
        },
        {
            "name": "Yves Rocher",
            "website": "https://www.yves-rocher.fr",
            "playstore_app_id": "com.ysl.yvesrocher",
            "appstore_app_id": "485296924",
            "instagram_username": "yvesrocherfr",
            "tiktok_username": "yvesrocher",
            "youtube_channel_id": "yvesrocherfr",
        },
        {
            "name": "L'Occitane",
            "website": "https://www.loccitane.com/fr-fr",
            "playstore_app_id": "com.loccitane.occtouch",
            "instagram_username": "loccitane",
            "tiktok_username": "loccitane_fr",
            "youtube_channel_id": "loccitaneenprovence",
        },
        {
            "name": "Lush",
            "website": "https://www.lush.com/fr",
            "playstore_app_id": "com.lush.app",
            "appstore_app_id": "946403534",
            "instagram_username": "lushfrance",
            "tiktok_username": "lush.france",
            "youtube_channel_id": "LushFrance",
        },
    ],
    "electromenager": [
        {
            "name": "Darty",
            "website": "https://www.darty.com",
            "playstore_app_id": "com.darty.app",
            "appstore_app_id": "352210890",
            "instagram_username": "darty_officiel",
            "tiktok_username": "darty_officiel",
            "youtube_channel_id": "UC_zgf8leGKSXNLLyCYP9PeQ",
        },
        {
            "name": "Boulanger",
            "website": "https://www.boulanger.com",
            "playstore_app_id": "fr.boulanger.shoppingapp",
            "appstore_app_id": "412042787",
            "instagram_username": "boulanger",
            "tiktok_username": "boulanger_officiel",
            "youtube_channel_id": "UCFZVM4GAdw71Uz4yejsa2cA",
        },
        {
            "name": "Fnac",
            "website": "https://www.fnac.com",
            "playstore_app_id": "com.fnac.android",
            "appstore_app_id": "378498309",
            "instagram_username": "fnac_officiel",
            "tiktok_username": "fnac_officiel",
            "youtube_channel_id": "UCH8T7mQypVa7EjJN9zbhc1w",
        },
        {
            "name": "Cdiscount",
            "website": "https://www.cdiscount.com",
            "playstore_app_id": "com.cdiscount.android",
            "appstore_app_id": "466271873",
            "instagram_username": "cdiscount",
            "tiktok_username": "cdiscount",
            "youtube_channel_id": "UC7Oo5ZMi8c-vf5KgjN92cxg",
        },
    ],
    "bricolage": [
        {
            "name": "Leroy Merlin",
            "website": "https://www.leroymerlin.fr",
            "playstore_app_id": "com.leroymerlin.franceapp",
            "appstore_app_id": "522478918",
            "instagram_username": "leroymerlin",
            "tiktok_username": "leroymerlin",
            "youtube_channel_id": "leroymerlin",
        },
        {
            "name": "Castorama",
            "website": "https://www.castorama.fr",
            "playstore_app_id": "com.castorama.selfcare",
            "appstore_app_id": "1163490666",
            "instagram_username": "castoramafrance",
            "tiktok_username": "castoramafrance",
            "youtube_channel_id": "castorama",
        },
        {
            "name": "Brico Dépôt",
            "website": "https://www.bricodepot.fr",
            "playstore_app_id": "com.bricodepot.android",
            "instagram_username": "bricodepot.france",
            "tiktok_username": "bricodepot",
            "youtube_channel_id": "UC7GZ6NqxeqHz0MnsllLEhbw",
        },
        {
            "name": "Mr Bricolage",
            "website": "https://www.mr-bricolage.fr",
            "playstore_app_id": "com.mrbricolage.android",
            "instagram_username": "mrbricolage_france",
            "youtube_channel_id": "UCaRV-cA9_f8XvNWZfPQa_gA",
        },
    ],
    "sport": [
        {
            "name": "Decathlon",
            "website": "https://www.decathlon.fr",
            "playstore_app_id": "com.decathlon.app",
            "appstore_app_id": "1079647629",
            "instagram_username": "decathlon",
            "tiktok_username": "decathlon",
            "youtube_channel_id": "decathlon",
        },
        {
            "name": "Go Sport",
            "website": "https://www.go-sport.com",
            "playstore_app_id": "com.gosport.android",
            "instagram_username": "go_sport",
            "tiktok_username": "gosport",
            "youtube_channel_id": "UCVMVu8p7bOES4VJyd5Q41aw",
        },
        {
            "name": "Intersport",
            "website": "https://www.intersport.fr",
            "playstore_app_id": "com.intersport.shop",
            "instagram_username": "intersportfrance",
            "tiktok_username": "intersportfrance",
            "youtube_channel_id": "UCDS_mA4bqfkCp1OqoMh_lGA",
        },
    ],
    "alimentaire_bio": [
        {
            "name": "Biocoop",
            "website": "https://www.biocoop.fr",
            "instagram_username": "biocoop_officiel",
        },
        {
            "name": "Naturalia",
            "website": "https://www.naturalia.fr",
            "playstore_app_id": "com.naturalia.android",
            "instagram_username": "naturalia_magasinsbio",
            "tiktok_username": "naturalia_magasins_bio",
            "youtube_channel_id": "UCGzDECCw_UGtKOwFH_bhBGQ",
        },
        {
            "name": "La Vie Claire",
            "website": "https://www.lavieclaire.com",
            "appstore_app_id": "1195077667",
            "instagram_username": "lavieclaire_bio",
            "tiktok_username": "la.vie.claire",
            "youtube_channel_id": "UCLgUFrMFrcVOXs6i1A8Y4hA",
        },
    ],
    "ameublement": [
        {
            "name": "Ikea",
            "website": "https://www.ikea.com/fr",
            "playstore_app_id": "com.ingka.ikea.app",
            "appstore_app_id": "391130855",
            "instagram_username": "ikeafrance",
            "tiktok_username": "ikeafrance",
            "youtube_channel_id": "UCXzI0Bp-qeP80W6C7dgsjOg",
        },
        {
            "name": "Maisons du Monde",
            "website": "https://www.maisonsdumonde.com",
            "playstore_app_id": "com.maisonsdumonde.app",
            "appstore_app_id": "594498498",
            "instagram_username": "maisonsdumonde",
            "tiktok_username": "maisonsdumonde",
            "youtube_channel_id": "UCvDz46dvR6tEJoHtmYPcmBA",
        },
        {
            "name": "Conforama",
            "website": "https://www.conforama.fr",
            "playstore_app_id": "fr.conforama.android",
            "appstore_app_id": "542498498",
            "instagram_username": "conforama_france",
            "tiktok_username": "conforama",
        },
        {
            "name": "But",
            "website": "https://www.but.fr",
            "playstore_app_id": "fr.but.android",
            "appstore_app_id": "668498498",
            "instagram_username": "but_officiel",
            "tiktok_username": "magasinsbut",
        },
        {
            "name": "La Redoute",
            "website": "https://www.laredoute.fr",
            "playstore_app_id": "com.laredoute.android",
            "appstore_app_id": "588498498",
            "instagram_username": "laredoute",
            "tiktok_username": "laredoute",
            "youtube_channel_id": "UC2pLRq0rtiQQku0YxntO2xw",
        },
        {
            "name": "Alinea",
            "website": "https://www.alinea.com",
            "instagram_username": "alinea_officiel",
        },
        {
            "name": "Habitat",
            "website": "https://www.habitat.fr",
            "instagram_username": "habitat_officiel",
            "tiktok_username": "habitat_france",
        },
    ],
}

SECTORS = [
    {"code": "supermarche", "name": "Supermarché / Hypermarché", "icon": "🛒"},
    {"code": "mode", "name": "Mode / Habillement", "icon": "👕"},
    {"code": "beaute", "name": "Beauté / Cosmétiques", "icon": "💄"},
    {"code": "electromenager", "name": "Électroménager / High-Tech", "icon": "📱"},
    {"code": "bricolage", "name": "Bricolage / Maison", "icon": "🔨"},
    {"code": "sport", "name": "Sport / Outdoor", "icon": "⚽"},
    {"code": "ameublement", "name": "Ameublement / Décoration", "icon": "🛋️"},
    {"code": "alimentaire_bio", "name": "Alimentaire Bio", "icon": "🌿"},
]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/sectors")
async def get_available_sectors():
    """Get list of available business sectors."""
    return {
        "sectors": SECTORS,
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
    if sector not in COMPETITORS_BY_SECTOR:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown sector. Available: {list(COMPETITORS_BY_SECTOR.keys())}"
        )

    suggestions = []
    existing_query = db.query(Competitor).filter(Competitor.is_active == True)
    if user:
        existing_query = existing_query.filter(Competitor.user_id == user.id)
    existing_names = {c.name.lower() for c in existing_query.all()}

    for comp in COMPETITORS_BY_SECTOR[sector]:
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
    if sector not in COMPETITORS_BY_SECTOR:
        raise HTTPException(status_code=400, detail=f"Unknown sector")

    # Get user's advertiser
    advertiser = db.query(Advertiser).filter(
        Advertiser.user_id == user.id, Advertiser.is_active == True
    ).first()

    added = []
    skipped = []

    for comp in COMPETITORS_BY_SECTOR[sector]:
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
    if sector not in COMPETITORS_BY_SECTOR:
        raise HTTPException(status_code=400, detail=f"Unknown sector")

    # Get user's advertiser
    advertiser = db.query(Advertiser).filter(
        Advertiser.user_id == user.id, Advertiser.is_active == True
    ).first()

    added = []
    not_found = []
    skipped = []

    sector_competitors = {c["name"].lower(): c for c in COMPETITORS_BY_SECTOR[sector]}

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
    for sector_comps in COMPETITORS_BY_SECTOR.values():
        for comp in sector_comps:
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
    if sector not in COMPETITORS_BY_SECTOR:
        return None

    for comp in COMPETITORS_BY_SECTOR[sector]:
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

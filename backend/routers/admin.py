"""
Admin backoffice router.
Platform stats accessible to all authenticated users (scoped to their data).
User management restricted to admins.
"""
import math
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import (
    get_db, User, Advertiser, Competitor,
    Ad, InstagramData, TikTokData, YouTubeData, AppData, StoreLocation,
    PromptTemplate, Store,
)
from core.auth import get_current_user
from services.scheduler import scheduler

router = APIRouter()


# ── Prompt Templates ──────────────────────────────────────────────────────────

class PromptUpdateRequest(BaseModel):
    prompt_text: str
    model_id: str | None = None
    max_tokens: int | None = None


@router.get("/prompts")
async def list_prompts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all editable AI prompt templates."""
    prompts = db.query(PromptTemplate).order_by(PromptTemplate.key).all()
    return [
        {
            "key": p.key,
            "label": p.label,
            "prompt_text": p.prompt_text,
            "model_id": p.model_id,
            "max_tokens": p.max_tokens,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in prompts
    ]


@router.put("/prompts/{key}")
async def update_prompt(
    key: str,
    body: PromptUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an AI prompt template."""
    prompt = db.query(PromptTemplate).filter(PromptTemplate.key == key).first()
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt '{key}' introuvable")
    prompt.prompt_text = body.prompt_text
    if body.model_id is not None:
        prompt.model_id = body.model_id
    if body.max_tokens is not None:
        prompt.max_tokens = body.max_tokens
    prompt.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(prompt)
    return {
        "key": prompt.key,
        "label": prompt.label,
        "prompt_text": prompt.prompt_text,
        "model_id": prompt.model_id,
        "max_tokens": prompt.max_tokens,
        "updated_at": prompt.updated_at.isoformat() if prompt.updated_at else None,
    }


# ── GPS Conflicts (BANCO vs stores) ──────────────────────────────────────────

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two GPS points."""
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@router.get("/gps-conflicts")
async def get_gps_conflicts(
    threshold: int = 200,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compare store GPS positions with BANCO data. Returns conflicts above threshold (meters)."""
    stores = db.query(Store).filter(
        Store.latitude.isnot(None),
        Store.longitude.isnot(None),
        Store.is_active == True,
    ).all()

    conflicts = []
    for store in stores:
        # Match by postal_code + fuzzy name
        banco_matches = db.query(StoreLocation).filter(
            StoreLocation.postal_code == store.postal_code,
            StoreLocation.latitude.isnot(None),
            StoreLocation.longitude.isnot(None),
        ).all()

        if not banco_matches:
            continue

        # Find closest BANCO match
        best = None
        best_dist = float("inf")
        for bl in banco_matches:
            dist = _haversine(store.latitude, store.longitude, bl.latitude, bl.longitude)
            if dist < best_dist:
                best_dist = dist
                best = bl

        if best and best_dist > threshold:
            conflicts.append({
                "store_id": store.id,
                "store_name": store.name,
                "city": store.city,
                "postal_code": store.postal_code,
                "store_lat": round(store.latitude, 6),
                "store_lng": round(store.longitude, 6),
                "banco_lat": round(best.latitude, 6),
                "banco_lng": round(best.longitude, 6),
                "banco_name": best.name,
                "distance_m": round(best_dist),
                "gps_verified": store.gps_verified or False,
            })

    total_stores = len(stores)
    conflicts.sort(key=lambda c: c["distance_m"], reverse=True)
    return {
        "total_stores": total_stores,
        "conflicts_count": len(conflicts),
        "threshold_m": threshold,
        "conflicts": conflicts,
    }


class GpsResolveRequest(BaseModel):
    chosen: str  # "store" or "banco"


@router.post("/gps-conflicts/{store_id}/resolve")
async def resolve_gps_conflict(
    store_id: int,
    body: GpsResolveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolve a GPS conflict by choosing store or BANCO coordinates."""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Magasin introuvable")

    if body.chosen == "banco":
        # Find the matching BANCO location
        banco = db.query(StoreLocation).filter(
            StoreLocation.postal_code == store.postal_code,
            StoreLocation.latitude.isnot(None),
        ).all()
        if not banco:
            raise HTTPException(status_code=404, detail="Aucune position BANCO trouvee")
        # Pick closest
        best = min(banco, key=lambda b: _haversine(
            store.latitude, store.longitude, b.latitude, b.longitude
        ))
        store.latitude = best.latitude
        store.longitude = best.longitude

    store.gps_verified = True
    db.commit()
    return {"message": f"Position {'BANCO' if body.chosen == 'banco' else 'magasin'} choisie", "store_id": store_id}


@router.get("/stats")
async def get_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Platform statistics scoped to the current user."""
    # User's competitors
    user_comp_ids = [
        row[0] for row in
        db.query(Competitor.id).filter(
            Competitor.user_id == user.id, Competitor.is_active == True
        ).all()
    ]

    total_brands = db.query(func.count(Advertiser.id)).filter(
        Advertiser.user_id == user.id, Advertiser.is_active == True
    ).scalar()
    total_competitors = len(user_comp_ids)

    # Data volume scoped to user's competitors
    if user_comp_ids:
        total_ads = db.query(func.count(Ad.id)).filter(Ad.competitor_id.in_(user_comp_ids)).scalar()
        total_instagram = db.query(func.count(InstagramData.id)).filter(InstagramData.competitor_id.in_(user_comp_ids)).scalar()
        total_tiktok = db.query(func.count(TikTokData.id)).filter(TikTokData.competitor_id.in_(user_comp_ids)).scalar()
        total_youtube = db.query(func.count(YouTubeData.id)).filter(YouTubeData.competitor_id.in_(user_comp_ids)).scalar()
        total_apps = db.query(func.count(AppData.id)).filter(AppData.competitor_id.in_(user_comp_ids)).scalar()
        total_stores = db.query(func.count(StoreLocation.id)).filter(StoreLocation.competitor_id.in_(user_comp_ids)).scalar()
    else:
        total_ads = total_instagram = total_tiktok = total_youtube = total_apps = total_stores = 0

    return {
        "brands": total_brands,
        "competitors": total_competitors,
        "data_volume": {
            "ads": total_ads,
            "instagram_records": total_instagram,
            "tiktok_records": total_tiktok,
            "youtube_records": total_youtube,
            "app_records": total_apps,
            "store_locations": total_stores,
        },
        "scheduler": scheduler.get_status(),
    }


@router.get("/data-audit")
async def audit_data(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Show ownership of all brands and competitors. Admin only."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")
    brands = db.query(Advertiser).filter(Advertiser.is_active == True).all()
    competitors = db.query(Competitor).filter(Competitor.is_active == True).all()
    users = {u.id: u.email for u in db.query(User).all()}

    return {
        "brands": [
            {
                "id": b.id,
                "company_name": b.company_name,
                "user_id": b.user_id,
                "user_email": users.get(b.user_id, "orphan"),
            }
            for b in brands
        ],
        "competitors": [
            {
                "id": c.id,
                "name": c.name,
                "user_id": c.user_id,
                "user_email": users.get(c.user_id, "orphan"),
            }
            for c in competitors
        ],
    }


@router.get("/users")
async def list_users(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all users with their brand/competitor info. Admin only."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")
    users = db.query(User).order_by(User.created_at.desc()).all()
    result = []
    for u in users:
        brand = db.query(Advertiser).filter(
            Advertiser.user_id == u.id, Advertiser.is_active == True
        ).first()
        competitors_count = db.query(func.count(Competitor.id)).filter(
            Competitor.user_id == u.id, Competitor.is_active == True
        ).scalar()
        result.append({
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "is_active": u.is_active,
            "is_admin": u.is_admin,
            "has_brand": brand is not None,
            "brand_name": brand.company_name if brand else None,
            "competitors_count": competitors_count,
        })
    return result

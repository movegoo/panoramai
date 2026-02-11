"""
Competitors management router.
CRUD operations for managing competitors.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional

from database import get_db, Competitor, AppData, InstagramData, TikTokData, YouTubeData, StoreLocation
from models.schemas import CompetitorCreate, CompetitorUpdate, CompetitorCard, CompetitorDetail, ChannelData, MetricValue, Alert
from core.trends import calculate_trend, TrendDirection

router = APIRouter()


def get_active_channels(comp: Competitor) -> List[str]:
    """Liste les canaux configurés pour un concurrent."""
    channels = []
    if comp.playstore_app_id:
        channels.append("playstore")
    if comp.appstore_app_id:
        channels.append("appstore")
    if comp.instagram_username:
        channels.append("instagram")
    if comp.tiktok_username:
        channels.append("tiktok")
    if comp.youtube_channel_id:
        channels.append("youtube")
    return channels


def calculate_score(
    app_rating: Optional[float],
    downloads: Optional[int],
    social_followers: Optional[int]
) -> float:
    """Calcule un score composite 0-100."""
    score = 0.0
    if app_rating:
        score += (app_rating / 5.0) * 40
    if social_followers:
        normalized = min(social_followers / 1_000_000, 1.0)
        score += normalized * 40
    if downloads:
        normalized = min(downloads / 10_000_000, 1.0)
        score += normalized * 20
    return round(score, 1)


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/dashboard")
async def get_dashboard(db: Session = Depends(get_db)):
    """
    Dashboard stats for the homepage.
    Returns aggregate metrics and recent activity.
    """
    from database import Ad

    competitors = db.query(Competitor).all()

    # Count totals
    total_competitors = len(competitors)
    total_ads = db.query(Ad).count()
    total_apps = sum(1 for c in competitors if c.playstore_app_id or c.appstore_app_id)
    total_instagram = sum(1 for c in competitors if c.instagram_username)

    # Recent activity (last app/instagram data)
    recent_activity = []

    recent_app_data = db.query(AppData).order_by(desc(AppData.recorded_at)).limit(5).all()
    for app in recent_app_data:
        comp = db.query(Competitor).filter(Competitor.id == app.competitor_id).first()
        if comp:
            recent_activity.append({
                "type": "app",
                "competitor": comp.name,
                "description": f"App data updated - Rating: {app.rating}",
                "date": app.recorded_at.isoformat() if app.recorded_at else None,
            })

    recent_insta = db.query(InstagramData).order_by(desc(InstagramData.recorded_at)).limit(5).all()
    for insta in recent_insta:
        comp = db.query(Competitor).filter(Competitor.id == insta.competitor_id).first()
        if comp:
            followers = insta.followers or 0
            recent_activity.append({
                "type": "instagram",
                "competitor": comp.name,
                "description": f"Instagram updated - {followers:,} followers",
                "date": insta.recorded_at.isoformat() if insta.recorded_at else None,
            })

    # Sort by date
    recent_activity.sort(key=lambda x: x["date"] or "", reverse=True)

    return {
        "total_competitors": total_competitors,
        "total_ads_tracked": total_ads,
        "total_apps_tracked": total_apps,
        "competitors_with_instagram": total_instagram,
        "recent_activity": recent_activity[:10],
    }


@router.get("/", response_model=List[CompetitorCard])
async def list_competitors(db: Session = Depends(get_db)):
    """
    Liste tous les concurrents avec leurs métriques clés.

    Retourne des cartes synthétiques avec score et ranking.
    """
    competitors = db.query(Competitor).filter(Competitor.is_active == True).all()
    cards = []

    for comp in competitors:
        # Dernières données
        playstore = db.query(AppData).filter(
            AppData.competitor_id == comp.id,
            AppData.store == "playstore"
        ).order_by(desc(AppData.recorded_at)).first()

        instagram = db.query(InstagramData).filter(
            InstagramData.competitor_id == comp.id
        ).order_by(desc(InstagramData.recorded_at)).first()

        tiktok = db.query(TikTokData).filter(
            TikTokData.competitor_id == comp.id
        ).order_by(desc(TikTokData.recorded_at)).first()

        youtube = db.query(YouTubeData).filter(
            YouTubeData.competitor_id == comp.id
        ).order_by(desc(YouTubeData.recorded_at)).first()

        # Calcul du score
        social_total = 0
        if instagram and instagram.followers:
            social_total += instagram.followers
        if tiktok and tiktok.followers:
            social_total += tiktok.followers
        if youtube and youtube.subscribers:
            social_total += youtube.subscribers

        score = calculate_score(
            playstore.rating if playstore else None,
            playstore.downloads_numeric if playstore else None,
            social_total if social_total > 0 else None,
        )

        cards.append({
            "id": comp.id,
            "name": comp.name,
            "website": comp.website,
            "facebook_page_id": comp.facebook_page_id,
            "instagram_username": comp.instagram_username,
            "tiktok_username": comp.tiktok_username,
            "youtube_channel_id": comp.youtube_channel_id,
            "playstore_app_id": comp.playstore_app_id,
            "appstore_app_id": comp.appstore_app_id,
            "global_score": score,
            "rank": 0,  # Sera calculé après tri
            "app_rating": playstore.rating if playstore else None,
            "app_downloads": playstore.downloads if playstore else None,
            "instagram_followers": instagram.followers if instagram else None,
            "tiktok_followers": tiktok.followers if tiktok else None,
            "youtube_subscribers": youtube.subscribers if youtube else None,
            "trend": None,
            "active_channels": get_active_channels(comp),
        })

    # Tri par score et assignation du rang
    cards.sort(key=lambda x: x["global_score"], reverse=True)
    for i, card in enumerate(cards):
        card["rank"] = i + 1

    return [CompetitorCard(**card) for card in cards]


@router.get("/{competitor_id}", response_model=CompetitorDetail)
async def get_competitor(competitor_id: int, db: Session = Depends(get_db)):
    """Profil détaillé d'un concurrent."""
    comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")

    # Récupère toutes les données
    playstore = db.query(AppData).filter(
        AppData.competitor_id == comp.id,
        AppData.store == "playstore"
    ).order_by(desc(AppData.recorded_at)).first()

    appstore = db.query(AppData).filter(
        AppData.competitor_id == comp.id,
        AppData.store == "appstore"
    ).order_by(desc(AppData.recorded_at)).first()

    instagram = db.query(InstagramData).filter(
        InstagramData.competitor_id == comp.id
    ).order_by(desc(InstagramData.recorded_at)).first()

    tiktok = db.query(TikTokData).filter(
        TikTokData.competitor_id == comp.id
    ).order_by(desc(TikTokData.recorded_at)).first()

    youtube = db.query(YouTubeData).filter(
        YouTubeData.competitor_id == comp.id
    ).order_by(desc(YouTubeData.recorded_at)).first()

    # Construit les données par canal
    channels = {}

    if playstore:
        channels["playstore"] = ChannelData(
            channel="playstore",
            is_configured=True,
            last_updated=playstore.recorded_at,
            metrics={
                "rating": MetricValue(value=playstore.rating or 0, label="Note"),
                "reviews": MetricValue(value=playstore.reviews_count or 0, label="Avis"),
            }
        )

    if appstore:
        channels["appstore"] = ChannelData(
            channel="appstore",
            is_configured=True,
            last_updated=appstore.recorded_at,
            metrics={
                "rating": MetricValue(value=appstore.rating or 0, label="Note"),
                "reviews": MetricValue(value=appstore.reviews_count or 0, label="Avis"),
            }
        )

    if instagram:
        channels["instagram"] = ChannelData(
            channel="instagram",
            is_configured=True,
            last_updated=instagram.recorded_at,
            metrics={
                "followers": MetricValue(value=instagram.followers or 0, label="Followers"),
                "engagement": MetricValue(value=instagram.engagement_rate or 0, label="Engagement %"),
            }
        )

    if tiktok:
        channels["tiktok"] = ChannelData(
            channel="tiktok",
            is_configured=True,
            last_updated=tiktok.recorded_at,
            metrics={
                "followers": MetricValue(value=tiktok.followers or 0, label="Followers"),
                "likes": MetricValue(value=tiktok.likes or 0, label="Likes"),
            }
        )

    if youtube:
        channels["youtube"] = ChannelData(
            channel="youtube",
            is_configured=True,
            last_updated=youtube.recorded_at,
            metrics={
                "subscribers": MetricValue(value=youtube.subscribers or 0, label="Abonnés"),
                "views": MetricValue(value=youtube.total_views or 0, label="Vues"),
            }
        )

    # Calcul du score et du rang
    all_competitors = db.query(Competitor).filter(Competitor.is_active == True).all()
    scores = []
    for c in all_competitors:
        ps = db.query(AppData).filter(AppData.competitor_id == c.id, AppData.store == "playstore").order_by(desc(AppData.recorded_at)).first()
        ig = db.query(InstagramData).filter(InstagramData.competitor_id == c.id).order_by(desc(InstagramData.recorded_at)).first()

        social = (ig.followers if ig else 0) or 0
        s = calculate_score(
            ps.rating if ps else None,
            ps.downloads_numeric if ps else None,
            social if social > 0 else None,
        )
        scores.append((c.id, s))

    scores.sort(key=lambda x: x[1], reverse=True)
    rank = next((i + 1 for i, (cid, _) in enumerate(scores) if cid == comp.id), 0)
    my_score = next((s for cid, s in scores if cid == comp.id), 0)

    return CompetitorDetail(
        id=comp.id,
        name=comp.name,
        website=comp.website,
        playstore_app_id=comp.playstore_app_id,
        appstore_app_id=comp.appstore_app_id,
        instagram_username=comp.instagram_username,
        tiktok_username=comp.tiktok_username,
        youtube_channel_id=comp.youtube_channel_id,
        global_score=my_score,
        rank=rank,
        channels=channels,
        recent_changes=[],
        created_at=comp.created_at,
    )


@router.post("/", response_model=CompetitorCard)
async def create_competitor(data: CompetitorCreate, db: Session = Depends(get_db)):
    """Ajoute un nouveau concurrent."""
    # Vérifie si le concurrent existe déjà
    existing = db.query(Competitor).filter(
        Competitor.name == data.name,
        Competitor.is_active == True
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail=f"Le concurrent '{data.name}' existe déjà")

    comp = Competitor(
        name=data.name,
        website=data.website,
        playstore_app_id=data.playstore_app_id,
        appstore_app_id=data.appstore_app_id,
        instagram_username=data.instagram_username,
        tiktok_username=data.tiktok_username,
        youtube_channel_id=data.youtube_channel_id,
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)

    # Auto-enrichissement BANCO (recherche magasins)
    try:
        from services.banco import banco_service
        stores_count = await banco_service.search_and_store(comp.id, comp.name, db)
        if stores_count > 0:
            import logging
            logging.getLogger(__name__).info(f"BANCO: {stores_count} magasins trouvés pour '{comp.name}'")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"BANCO enrichment failed for '{comp.name}': {e}")

    return CompetitorCard(
        id=comp.id,
        name=comp.name,
        website=comp.website,
        facebook_page_id=comp.facebook_page_id,
        instagram_username=comp.instagram_username,
        tiktok_username=comp.tiktok_username,
        youtube_channel_id=comp.youtube_channel_id,
        playstore_app_id=comp.playstore_app_id,
        appstore_app_id=comp.appstore_app_id,
        global_score=0,
        rank=db.query(Competitor).filter(Competitor.is_active == True).count(),
        active_channels=get_active_channels(comp),
    )


@router.put("/{competitor_id}")
async def update_competitor(
    competitor_id: int,
    data: CompetitorUpdate,
    db: Session = Depends(get_db)
):
    """
    Met à jour les identifiants d'un concurrent.

    Permet de corriger les app IDs, usernames, etc.
    """
    comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(comp, field, value)

    db.commit()
    db.refresh(comp)

    return {
        "message": f"Concurrent '{comp.name}' mis à jour",
        "updated_fields": list(update_data.keys()),
        "competitor": {
            "id": comp.id,
            "name": comp.name,
            "playstore_app_id": comp.playstore_app_id,
            "appstore_app_id": comp.appstore_app_id,
            "instagram_username": comp.instagram_username,
            "tiktok_username": comp.tiktok_username,
            "youtube_channel_id": comp.youtube_channel_id,
        }
    }


@router.delete("/{competitor_id}")
async def delete_competitor(competitor_id: int, db: Session = Depends(get_db)):
    """Supprime un concurrent (soft delete)."""
    comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")

    comp.is_active = False
    db.commit()

    return {"message": f"Concurrent '{comp.name}' supprimé"}


# =============================================================================
# Endpoints - Magasins concurrents
# =============================================================================

@router.get("/{competitor_id}/stores")
async def get_competitor_stores(competitor_id: int, db: Session = Depends(get_db)):
    """Liste les magasins d'un concurrent."""
    comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")

    stores = db.query(StoreLocation).filter(
        StoreLocation.competitor_id == competitor_id,
        StoreLocation.source == "BANCO"
    ).all()

    return {
        "competitor_id": competitor_id,
        "competitor_name": comp.name,
        "total": len(stores),
        "stores": [
            {
                "id": s.id,
                "name": s.name,
                "brand_name": s.brand_name,
                "category": s.category,
                "address": s.address,
                "postal_code": s.postal_code,
                "city": s.city,
                "department": s.department,
                "latitude": s.latitude,
                "longitude": s.longitude,
            }
            for s in stores
        ],
    }


@router.post("/{competitor_id}/refresh-stores")
async def refresh_competitor_stores(competitor_id: int, db: Session = Depends(get_db)):
    """Relance la recherche de magasins pour un concurrent."""
    comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")

    from services.banco import banco_service
    count = await banco_service.search_and_store(comp.id, comp.name, db)

    return {
        "message": f"{count} magasins trouvés pour '{comp.name}'",
        "competitor_id": competitor_id,
        "stores_count": count,
    }

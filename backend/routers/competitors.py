"""
Competitors management router.
CRUD operations for managing competitors.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional, Dict

import json
from database import get_db, Ad, Competitor, AppData, InstagramData, TikTokData, YouTubeData, StoreLocation, User, AdvertiserCompetitor, UserAdvertiser
from models.schemas import CompetitorCreate, CompetitorUpdate, CompetitorCard, CompetitorDetail, ChannelData, MetricValue, Alert
from core.trends import calculate_trend, TrendDirection
from core.auth import get_current_user
from core.utils import get_logo_url
from core.permissions import get_advertiser_competitors, get_advertiser_competitor_ids, parse_advertiser_header


def _scoped_competitor_query(db, user, x_advertiser_id=None, include_brand=False):
    """Build a competitor query scoped via advertiser join tables."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    if adv_id:
        query = (
            db.query(Competitor)
            .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
            .filter(AdvertiserCompetitor.advertiser_id == adv_id, Competitor.is_active == True)
        )
    elif user:
        user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
        if user_adv_ids:
            query = (
                db.query(Competitor)
                .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
                .filter(AdvertiserCompetitor.advertiser_id.in_(user_adv_ids), Competitor.is_active == True)
            )
        else:
            query = db.query(Competitor).filter(Competitor.id == -1)  # empty result
    else:
        query = db.query(Competitor).filter(Competitor.is_active == True)
    if not include_brand:
        query = query.filter((Competitor.is_brand == False) | (Competitor.is_brand == None))
    return query

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
    if comp.snapchat_entity_name:
        channels.append("snapchat")
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

@router.get("/lookup")
async def lookup_competitor(q: str = ""):
    """
    Search the built-in competitor database by name.
    Returns matching competitors with pre-filled social handles and app IDs.
    Used by the frontend to auto-suggest fields when adding a competitor.
    """
    from core.sectors import SECTORS as SECTORS_DB

    if not q or len(q) < 2:
        return []

    q_lower = q.lower().strip()
    results = []
    seen = set()
    for sector, sector_data in SECTORS_DB.items():
        for comp in sector_data.get("competitors", []):
            name_lower = comp["name"].lower()
            if q_lower in name_lower and name_lower not in seen:
                seen.add(name_lower)
                results.append({**comp, "sector": sector})
    # Sort: exact prefix match first, then alphabetical
    results.sort(key=lambda c: (0 if c["name"].lower().startswith(q_lower) else 1, c["name"]))
    return results[:10]


@router.get("/dashboard")
async def get_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Dashboard stats for the homepage.
    Returns aggregate metrics and recent activity.
    """
    from database import Ad

    competitors = _scoped_competitor_query(db, user, x_advertiser_id).all()
    comp_ids = [c.id for c in competitors]

    # Count totals
    total_competitors = len(competitors)
    total_ads = db.query(Ad).filter(Ad.competitor_id.in_(comp_ids)).count() if comp_ids else 0
    total_apps = sum(1 for c in competitors if c.playstore_app_id or c.appstore_app_id)
    total_instagram = sum(1 for c in competitors if c.instagram_username)

    # Recent activity (last app/instagram data)
    recent_activity = []

    # Build competitor name lookup
    comp_names = {c.id: c.name for c in competitors}

    if comp_ids:
        recent_app_data = db.query(AppData).filter(
            AppData.competitor_id.in_(comp_ids)
        ).order_by(desc(AppData.recorded_at)).limit(5).all()
        for app in recent_app_data:
            name = comp_names.get(app.competitor_id)
            if name:
                recent_activity.append({
                    "type": "app",
                    "competitor": name,
                    "description": f"App data updated - Rating: {app.rating}",
                    "date": app.recorded_at.isoformat() if app.recorded_at else None,
                })

        recent_insta = db.query(InstagramData).filter(
            InstagramData.competitor_id.in_(comp_ids)
        ).order_by(desc(InstagramData.recorded_at)).limit(5).all()
        for insta in recent_insta:
            name = comp_names.get(insta.competitor_id)
            if name:
                followers = insta.followers or 0
                recent_activity.append({
                    "type": "instagram",
                    "competitor": name,
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


@router.get("/")
async def list_competitors(
    include_brand: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Liste tous les concurrents avec leurs métriques clés.

    Retourne des cartes synthétiques avec score et ranking.
    """
    # Auto-patch missing handles from built-in competitor database
    from core.sectors import SECTORS as SECTORS_DB
    known = {}
    for sector_data in SECTORS_DB.values():
        for comp in sector_data.get("competitors", []):
            known[comp["name"].lower()] = comp

    all_comps = _scoped_competitor_query(db, user, x_advertiser_id, include_brand=True).all()
    patched = False
    for comp in all_comps:
        ref = known.get(comp.name.lower())
        if not ref:
            continue
        for f in ["facebook_page_id", "playstore_app_id", "appstore_app_id", "instagram_username",
                  "tiktok_username", "youtube_channel_id", "snapchat_entity_name", "website"]:
            if ref.get(f) and not getattr(comp, f, None):
                setattr(comp, f, ref[f])
                patched = True
    if patched:
        db.commit()

    competitors = _scoped_competitor_query(db, user, x_advertiser_id, include_brand=include_brand).all()
    comp_ids = [c.id for c in competitors]
    cards = []

    # Batch-load latest data for all competitors (4 queries instead of 4*N)
    from routers.watch import _batch_load_latest
    ps_map = _batch_load_latest(db, AppData, comp_ids, AppData.store == "playstore")
    ig_map = _batch_load_latest(db, InstagramData, comp_ids)
    tt_map = _batch_load_latest(db, TikTokData, comp_ids)
    yt_map = _batch_load_latest(db, YouTubeData, comp_ids)

    for comp in competitors:
        playstore = ps_map.get(comp.id)
        instagram = ig_map.get(comp.id)
        tiktok = tt_map.get(comp.id)
        youtube = yt_map.get(comp.id)

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
            "logo_url": get_logo_url(comp.website),
            "facebook_page_id": comp.facebook_page_id,
            "instagram_username": comp.instagram_username,
            "tiktok_username": comp.tiktok_username,
            "youtube_channel_id": comp.youtube_channel_id,
            "playstore_app_id": comp.playstore_app_id,
            "appstore_app_id": comp.appstore_app_id,
            "snapchat_entity_name": comp.snapchat_entity_name,
            "global_score": score,
            "rank": 0,  # Sera calculé après tri
            "app_rating": playstore.rating if playstore else None,
            "app_downloads": playstore.downloads if playstore else None,
            "instagram_followers": instagram.followers if instagram else None,
            "tiktok_followers": tiktok.followers if tiktok else None,
            "youtube_subscribers": youtube.subscribers if youtube else None,
            "trend": None,
            "active_channels": get_active_channels(comp),
            "created_at": comp.created_at,
        })

    # Tri par score et assignation du rang
    cards.sort(key=lambda x: x["global_score"], reverse=True)
    for i, card in enumerate(cards):
        card["rank"] = i + 1

    return [CompetitorCard(**card) for card in cards]


@router.get("/{competitor_id}")
async def get_competitor(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Profil détaillé d'un concurrent."""
    from core.permissions import verify_competitor_ownership
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp = verify_competitor_ownership(db, competitor_id, user, advertiser_id=adv_id)

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

    # Calcul du score et du rang (scoped to advertiser)
    all_competitors = _scoped_competitor_query(db, user, x_advertiser_id, include_brand=True).all()
    all_ids = [c.id for c in all_competitors]
    from routers.watch import _batch_load_latest
    all_ps = _batch_load_latest(db, AppData, all_ids, AppData.store == "playstore")
    all_ig = _batch_load_latest(db, InstagramData, all_ids)

    scores = []
    for c in all_competitors:
        ps = all_ps.get(c.id)
        ig = all_ig.get(c.id)

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
        snapchat_entity_name=comp.snapchat_entity_name,
        global_score=my_score,
        rank=rank,
        channels=channels,
        recent_changes=[],
        created_at=comp.created_at,
    )


@router.post("/")
async def create_competitor(
    data: CompetitorCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Ajoute un nouveau concurrent (avec déduplication)."""
    adv_id = parse_advertiser_header(x_advertiser_id)

    # Check if already linked to this advertiser
    if adv_id:
        existing_link = (
            db.query(AdvertiserCompetitor)
            .join(Competitor, Competitor.id == AdvertiserCompetitor.competitor_id)
            .filter(
                AdvertiserCompetitor.advertiser_id == adv_id,
                Competitor.is_active == True,
                func.lower(Competitor.name) == data.name.lower(),
            )
            .first()
        )
        if existing_link:
            raise HTTPException(status_code=400, detail=f"Le concurrent '{data.name}' existe déjà")

    # Deduplication: look for existing competitor
    comp = None
    if data.facebook_page_id:
        comp = db.query(Competitor).filter(
            Competitor.facebook_page_id == data.facebook_page_id,
            Competitor.is_active == True,
        ).first()
    if not comp and data.website:
        comp = db.query(Competitor).filter(
            Competitor.website == data.website,
            Competitor.is_active == True,
        ).first()
    if not comp:
        comp = db.query(Competitor).filter(
            func.lower(Competitor.name) == data.name.lower(),
            Competitor.is_active == True,
        ).first()

    if not comp:
        # Create new competitor
        comp = Competitor(
            name=data.name,
            website=data.website,
            facebook_page_id=data.facebook_page_id,
            playstore_app_id=data.playstore_app_id,
            appstore_app_id=data.appstore_app_id,
            instagram_username=data.instagram_username,
            tiktok_username=data.tiktok_username,
            youtube_channel_id=data.youtube_channel_id,
            snapchat_entity_name=data.snapchat_entity_name,
        )
        db.add(comp)
        db.flush()
    else:
        # Complement missing fields
        for f in ["website", "facebook_page_id", "playstore_app_id", "appstore_app_id",
                   "instagram_username", "tiktok_username", "youtube_channel_id", "snapchat_entity_name"]:
            new_val = getattr(data, f, None)
            if new_val and not getattr(comp, f, None):
                setattr(comp, f, new_val)

    # Create advertiser link
    if adv_id:
        existing = db.query(AdvertiserCompetitor).filter(
            AdvertiserCompetitor.advertiser_id == adv_id,
            AdvertiserCompetitor.competitor_id == comp.id,
        ).first()
        if not existing:
            db.add(AdvertiserCompetitor(advertiser_id=adv_id, competitor_id=comp.id))

    db.commit()
    db.refresh(comp)

    # Auto-fetch all data synchronously (reliable, no silent failures)
    try:
        await _auto_enrich_competitor(comp.id, comp)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Auto-enrich failed for '{comp.name}': {e}")

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
        snapchat_entity_name=comp.snapchat_entity_name,
        global_score=0,
        rank=len(get_advertiser_competitor_ids(db, adv_id)) if adv_id else 0,
        active_channels=get_active_channels(comp),
    )


@router.put("/{competitor_id}")
async def update_competitor(
    competitor_id: int,
    data: CompetitorUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Met à jour les identifiants d'un concurrent.

    Permet de corriger les app IDs, usernames, etc.
    Enrichit automatiquement les nouvelles sources ajoutées.
    """
    from core.permissions import verify_competitor_ownership, parse_advertiser_header
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp = verify_competitor_ownership(db, competitor_id, user, advertiser_id=adv_id)

    # Track which fields are being added (were empty, now have a value)
    new_fields = []
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        old_val = getattr(comp, field, None)
        if not old_val and value:
            new_fields.append(field)
        setattr(comp, field, value)

    db.commit()
    db.refresh(comp)

    # Synchronous enrichment for newly added fields (not fire-and-forget)
    enrich_results = {}
    if new_fields:
        enrich_results = await _auto_enrich_competitor(comp.id, comp)

    return {
        "message": f"Concurrent '{comp.name}' mis à jour" + (f" — enrichissement: {len(enrich_results)} sources" if enrich_results else ""),
        "updated_fields": list(update_data.keys()),
        "new_fields": new_fields,
        "enrichment": enrich_results,
        "competitor": {
            "id": comp.id,
            "name": comp.name,
            "facebook_page_id": comp.facebook_page_id,
            "playstore_app_id": comp.playstore_app_id,
            "appstore_app_id": comp.appstore_app_id,
            "instagram_username": comp.instagram_username,
            "tiktok_username": comp.tiktok_username,
            "youtube_channel_id": comp.youtube_channel_id,
        }
    }


@router.delete("/{competitor_id}")
async def delete_competitor(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Supprime un concurrent (retire le lien advertiser, soft-delete si plus aucun lien)."""
    from core.permissions import verify_competitor_ownership
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp = verify_competitor_ownership(db, competitor_id, user, advertiser_id=adv_id)

    # Remove the advertiser link
    if adv_id:
        db.query(AdvertiserCompetitor).filter(
            AdvertiserCompetitor.advertiser_id == adv_id,
            AdvertiserCompetitor.competitor_id == competitor_id,
        ).delete()
    else:
        # Remove all links for this user's advertisers
        user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
        if user_adv_ids:
            db.query(AdvertiserCompetitor).filter(
                AdvertiserCompetitor.advertiser_id.in_(user_adv_ids),
                AdvertiserCompetitor.competitor_id == competitor_id,
            ).delete(synchronize_session=False)

    # Soft-delete if no advertisers remain linked
    remaining = db.query(AdvertiserCompetitor).filter(AdvertiserCompetitor.competitor_id == competitor_id).count()
    if remaining == 0:
        comp.is_active = False

    db.commit()

    return {"message": f"Concurrent '{comp.name}' supprimé"}


# =============================================================================
# Endpoints - Magasins concurrents
# =============================================================================

@router.get("/{competitor_id}/stores")
async def get_competitor_stores(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Liste les magasins d'un concurrent."""
    from core.permissions import verify_competitor_ownership, parse_advertiser_header
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp = verify_competitor_ownership(db, competitor_id, user, advertiser_id=adv_id)

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
async def refresh_competitor_stores(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Relance la recherche de magasins pour un concurrent."""
    from core.permissions import verify_competitor_ownership, parse_advertiser_header
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp = verify_competitor_ownership(db, competitor_id, user, advertiser_id=adv_id)

    from services.banco import banco_service
    count = await banco_service.search_and_store(comp.id, comp.name, db)

    return {
        "message": f"{count} magasins trouvés pour '{comp.name}'",
        "competitor_id": competitor_id,
        "stores_count": count,
    }


@router.post("/{competitor_id}/enrich")
async def enrich_competitor(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Force re-enrichment of a competitor's data (social, apps, ads).
    Runs synchronously so the caller knows when it's done.
    """
    from core.permissions import verify_competitor_ownership, parse_advertiser_header
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp = verify_competitor_ownership(db, competitor_id, user, advertiser_id=adv_id)

    results = await _auto_enrich_competitor(comp.id, comp)
    return {
        "message": f"Enrichissement terminé pour '{comp.name}'",
        "results": results,
    }


@router.post("/{competitor_id}/suggest-child-pages")
async def suggest_child_pages(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Analyze existing ads to find potential child pages (pages filles).
    A child page is a Facebook page with a different page_id but a similar
    page_name to the competitor (e.g. regional or product sub-pages).
    """
    from core.permissions import verify_competitor_ownership, parse_advertiser_header
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp = verify_competitor_ownership(db, competitor_id, user, advertiser_id=adv_id)

    # Get the main page_id
    main_page_id = comp.facebook_page_id

    # Find all distinct page_ids in this competitor's ads
    ads = db.query(Ad).filter(Ad.competitor_id == competitor_id, Ad.page_id.isnot(None)).all()
    page_map: dict[str, dict] = {}
    for ad in ads:
        pid = ad.page_id
        if pid and pid not in page_map:
            page_map[pid] = {"page_id": pid, "page_name": ad.page_name or "Inconnu", "ad_count": 0}
        if pid:
            page_map[pid]["ad_count"] += 1

    # Already tracked child pages
    existing_children = set()
    if comp.child_page_ids:
        try:
            existing_children = set(json.loads(comp.child_page_ids))
        except (json.JSONDecodeError, TypeError):
            pass

    # Also look for ads from all competitors that share a similar page name
    comp_name = comp.name.lower()
    similar_ads = db.query(Ad.page_id, Ad.page_name).filter(
        Ad.page_id.isnot(None),
        Ad.page_name.isnot(None),
    ).distinct().all()

    for pid, pname in similar_ads:
        if pid and pname and pid not in page_map:
            pname_lower = pname.lower()
            # Check if page_name contains the competitor name or vice versa
            if (comp_name in pname_lower or pname_lower.startswith(comp_name[:4])) and pid != main_page_id:
                page_map[pid] = {"page_id": pid, "page_name": pname, "ad_count": 0}

    # Filter: exclude main page, mark already tracked
    suggestions = []
    for pid, info in page_map.items():
        if pid == main_page_id:
            continue
        info["already_tracked"] = pid in existing_children
        suggestions.append(info)

    suggestions.sort(key=lambda x: x["ad_count"], reverse=True)

    return {
        "competitor_id": competitor_id,
        "competitor_name": comp.name,
        "main_page_id": main_page_id,
        "suggestions": suggestions,
        "existing_children": sorted(existing_children),
    }


# =============================================================================
# Background auto-enrichment
# =============================================================================

async def _auto_enrich_competitor(competitor_id: int, comp: Competitor) -> dict:
    """Fetch all data for a competitor. Returns a summary dict."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Auto-enrichment started for '{comp.name}' (id={competitor_id})")
    results = {}

    # BANCO stores
    try:
        from services.banco import banco_service
        db = next(get_db())
        try:
            count = await banco_service.search_and_store(competitor_id, comp.name, db)
            logger.info(f"BANCO: {count} stores for '{comp.name}'")
            results["stores"] = count
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"BANCO failed for '{comp.name}': {e}")
        results["stores_error"] = str(e)

    # Facebook/Instagram Ads — use company/ads endpoint with page_id
    try:
        from services.scrapecreators import scrapecreators
        from routers.facebook import _name_matches, _parse_date
        from database import Ad, SessionLocal, Competitor as CompModel
        import json

        # Auto-resolve facebook_page_id if missing
        page_id = comp.facebook_page_id
        if not page_id:
            search_res = await scrapecreators.search_facebook_companies(comp.name)
            if search_res.get("success") and search_res.get("companies"):
                companies = search_res["companies"]
                best = None
                for c in companies:
                    c_name = (c.get("page_name") or c.get("name") or "").lower()
                    if comp.name.lower() in c_name or c_name in comp.name.lower():
                        best = c
                        break
                if not best and companies:
                    best = companies[0]
                page_id = str(best.get("page_id") or best.get("pageId") or best.get("id") or "") if best else ""
                if page_id:
                    db = SessionLocal()
                    try:
                        db_comp = db.query(CompModel).filter(CompModel.id == competitor_id).first()
                        if db_comp:
                            db_comp.facebook_page_id = page_id
                            db.commit()
                            logger.info(f"Auto-resolved facebook_page_id={page_id} for '{comp.name}'")
                    finally:
                        db.close()

        # Fetch ads via page_id or keyword search
        if page_id:
            result = await scrapecreators.fetch_facebook_company_ads(page_id=page_id)
        else:
            result = await scrapecreators.search_facebook_ads(company_name=comp.name, country="FR", limit=50)

        if result.get("success"):
            db = SessionLocal()
            try:
                new_count = 0
                for ad in result.get("ads", []):
                    ad_id = str(ad.get("ad_archive_id", ""))
                    if not ad_id:
                        continue
                    snapshot = ad.get("snapshot", {})
                    page_name = snapshot.get("page_name", "") or ad.get("page_name", "")
                    # When using page_id, all results belong to this competitor
                    if not page_id and not _name_matches(comp.name, page_name):
                        continue
                    if db.query(Ad).filter(Ad.ad_id == ad_id).first():
                        continue

                    cards = snapshot.get("cards", [])
                    fc = cards[0] if cards else {}
                    start_date = _parse_date(ad.get("start_date_string") or ad.get("start_date"))
                    end_date = _parse_date(ad.get("end_date_string") or ad.get("end_date"))
                    pubs = ad.get("publisher_platform", [])
                    if not isinstance(pubs, list):
                        pubs = [pubs] if pubs else []

                    new_ad = Ad(
                        competitor_id=competitor_id,
                        ad_id=ad_id,
                        platform="instagram" if any("INSTAGRAM" in str(p).upper() for p in pubs) else "facebook",
                        creative_url=fc.get("original_image_url") or fc.get("resized_image_url") or "",
                        ad_text=fc.get("body") or snapshot.get("body", {}).get("text", "") or "",
                        cta=fc.get("cta_text") or "",
                        start_date=start_date,
                        end_date=end_date,
                        is_active=ad.get("is_active", not bool(end_date)),
                        page_name=page_name or None,
                        ad_library_url=ad.get("url", "") or None,
                    )
                    db.add(new_ad)
                    new_count += 1
                if new_count:
                    db.commit()
                logger.info(f"Ads: {new_count} new for '{comp.name}'")
                results["ads"] = new_count
            finally:
                db.close()
    except Exception as e:
        logger.warning(f"Ads fetch failed for '{comp.name}': {e}")
        results["ads_error"] = str(e)

    # Instagram
    if comp.instagram_username:
        try:
            from services.scrapecreators import scrapecreators
            from database import SessionLocal
            result = await scrapecreators.fetch_instagram_profile(comp.instagram_username)
            if result.get("success"):
                db = SessionLocal()
                try:
                    db.add(InstagramData(
                        competitor_id=competitor_id,
                        followers=result.get("followers", 0),
                        following=result.get("following", 0),
                        posts_count=result.get("posts_count", 0),
                        avg_likes=result.get("avg_likes", 0),
                        avg_comments=result.get("avg_comments", 0),
                        engagement_rate=result.get("engagement_rate", 0),
                        bio=result.get("bio"),
                    ))
                    db.commit()
                    logger.info(f"Instagram fetched for '{comp.name}'")
                    results["instagram"] = result.get("followers", 0)
                finally:
                    db.close()
            else:
                results["instagram_error"] = result.get("error", "Failed")
        except Exception as e:
            logger.warning(f"Instagram failed for '{comp.name}': {e}")
            results["instagram_error"] = str(e)
    else:
        results["instagram"] = "no_username"

    # TikTok
    if comp.tiktok_username:
        try:
            from services.tiktok_scraper import tiktok_scraper
            from database import SessionLocal
            result = await tiktok_scraper.fetch_profile(comp.tiktok_username)
            if result.get("success"):
                db = SessionLocal()
                try:
                    db.add(TikTokData(
                        competitor_id=competitor_id,
                        username=comp.tiktok_username,
                        followers=result.get("followers", 0),
                        following=result.get("following", 0),
                        likes=result.get("likes", 0),
                        videos_count=result.get("videos_count", 0),
                        bio=result.get("bio"),
                        verified=result.get("verified", False),
                    ))
                    db.commit()
                    logger.info(f"TikTok fetched for '{comp.name}'")
                    results["tiktok"] = result.get("followers", 0)
                finally:
                    db.close()
            else:
                results["tiktok_error"] = result.get("error", "Failed")
        except Exception as e:
            logger.warning(f"TikTok failed for '{comp.name}': {e}")
            results["tiktok_error"] = str(e)
    else:
        results["tiktok"] = "no_username"

    # Play Store
    if comp.playstore_app_id:
        try:
            from routers.playstore import fetch_playstore_app
            from core.trends import parse_download_count
            from database import SessionLocal
            result = fetch_playstore_app(comp.playstore_app_id)
            if result.get("success"):
                db = SessionLocal()
                try:
                    db.add(AppData(
                        competitor_id=competitor_id,
                        store="playstore",
                        app_id=comp.playstore_app_id,
                        app_name=result["app_name"],
                        rating=result["rating"],
                        reviews_count=result["reviews_count"],
                        downloads=result["downloads"],
                        downloads_numeric=parse_download_count(result["downloads"]),
                        version=result["version"],
                        last_updated=result["last_updated"],
                        description=result["description"],
                        changelog=result["changelog"],
                    ))
                    db.commit()
                    logger.info(f"Play Store fetched for '{comp.name}'")
                    results["playstore"] = result["app_name"]
                finally:
                    db.close()
            else:
                results["playstore_error"] = result.get("error", "Failed")
        except Exception as e:
            logger.warning(f"Play Store failed for '{comp.name}': {e}")
            results["playstore_error"] = str(e)
    else:
        results["playstore"] = "no_app_id"

    # App Store
    if comp.appstore_app_id:
        try:
            from routers.appstore import fetch_appstore_app
            from database import SessionLocal
            result = await fetch_appstore_app(comp.appstore_app_id)
            if result.get("success"):
                db = SessionLocal()
                try:
                    db.add(AppData(
                        competitor_id=competitor_id,
                        store="appstore",
                        app_id=comp.appstore_app_id,
                        app_name=result["app_name"],
                        rating=result["rating"],
                        reviews_count=result["reviews_count"],
                        version=result["version"],
                        last_updated=result["last_updated"],
                        description=result["description"],
                        changelog=result["changelog"],
                    ))
                    db.commit()
                    logger.info(f"App Store fetched for '{comp.name}'")
                    results["appstore"] = result["app_name"]
                finally:
                    db.close()
            else:
                results["appstore_error"] = result.get("error", "Failed")
        except Exception as e:
            logger.warning(f"App Store failed for '{comp.name}': {e}")
            results["appstore_error"] = str(e)
    else:
        results["appstore"] = "no_app_id"

    # YouTube
    if comp.youtube_channel_id:
        try:
            from services.youtube_api import youtube_api
            from database import SessionLocal
            result = await youtube_api.get_channel_analytics(comp.youtube_channel_id)
            if result.get("success"):
                analytics = result.get("analytics", {})
                db = SessionLocal()
                try:
                    db.add(YouTubeData(
                        competitor_id=competitor_id,
                        channel_id=comp.youtube_channel_id,
                        channel_name=result.get("channel_name"),
                        subscribers=result.get("subscribers", 0),
                        total_views=result.get("total_views", 0),
                        videos_count=result.get("videos_count", 0),
                        avg_views=analytics.get("avg_views", 0),
                        avg_likes=analytics.get("avg_likes", 0),
                        avg_comments=analytics.get("avg_comments", 0),
                        engagement_rate=analytics.get("engagement_rate", 0),
                        description=result.get("description"),
                    ))
                    db.commit()
                    logger.info(f"YouTube fetched for '{comp.name}'")
                    results["youtube"] = result.get("subscribers", 0)
                finally:
                    db.close()
            else:
                results["youtube_error"] = result.get("error", "Failed")
        except Exception as e:
            logger.warning(f"YouTube failed for '{comp.name}': {e}")
            results["youtube_error"] = str(e)
    else:
        results["youtube"] = "no_channel_id"

    # Google Ads (via domain)
    if comp.website:
        try:
            from routers.google_ads import _fetch_and_store_google_ads, _extract_domain
            from database import SessionLocal
            domain = _extract_domain(comp.website)
            if domain:
                db = SessionLocal()
                try:
                    new, updated, fetched = await _fetch_and_store_google_ads(
                        competitor_id=competitor_id, domain=domain, country="FR", db=db
                    )
                    logger.info(f"Google Ads: {new} new, {updated} updated for '{comp.name}'")
                    results["google_ads"] = new
                finally:
                    db.close()
        except Exception as e:
            logger.warning(f"Google Ads failed for '{comp.name}': {e}")
            results["google_ads_error"] = str(e)

    # Snapchat Ads (via Apify)
    snap_query = comp.snapchat_entity_name or comp.name
    try:
        from services.apify_snapchat import apify_snapchat
        from database import SessionLocal
        snap_result = await apify_snapchat.search_snapchat_ads(query=snap_query)
        if snap_result.get("success"):
            db = SessionLocal()
            try:
                new_count = 0
                for ad in snap_result.get("ads", []):
                    ad_id = ad.get("snap_id", "")
                    if not ad_id:
                        continue
                    if db.query(Ad).filter(Ad.ad_id == ad_id).first():
                        continue
                    new_ad = Ad(
                        competitor_id=competitor_id,
                        ad_id=ad_id,
                        platform="snapchat",
                        creative_url=ad.get("creative_url", ""),
                        ad_text=ad.get("ad_text", ""),
                        title=ad.get("title", "")[:200] if ad.get("title") else None,
                        start_date=ad.get("start_date"),
                        is_active=ad.get("is_active", False),
                        impressions_min=ad.get("impressions", 0),
                        impressions_max=ad.get("impressions", 0),
                        publisher_platforms=json.dumps(["SNAPCHAT"]),
                        page_name=ad.get("page_name", ""),
                        display_format=ad.get("display_format", "SNAP"),
                        ad_library_url="https://adsgallery.snap.com/",
                    )
                    db.add(new_ad)
                    new_count += 1
                if new_count:
                    db.commit()

                # Auto-discover entity name if not set
                if not comp.snapchat_entity_name and snap_result.get("ads"):
                    names: dict[str, int] = {}
                    for ad in snap_result["ads"]:
                        pn = (ad.get("page_name") or "").strip()
                        if pn:
                            names[pn] = names.get(pn, 0) + 1
                    if names:
                        best_name = max(names, key=names.get)
                        db_comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
                        if db_comp:
                            db_comp.snapchat_entity_name = best_name
                            db.commit()
                            logger.info(f"Auto-discovered snapchat_entity_name='{best_name}' for '{comp.name}'")

                logger.info(f"Snapchat Ads: {new_count} new for '{comp.name}'")
                results["snapchat_ads"] = new_count
            finally:
                db.close()
        else:
            results["snapchat_ads_error"] = snap_result.get("error", "Failed")
    except Exception as e:
        logger.warning(f"Snapchat Ads failed for '{comp.name}': {e}")
        results["snapchat_ads_error"] = str(e)

    logger.info(f"Auto-enrichment complete for '{comp.name}'")
    return results

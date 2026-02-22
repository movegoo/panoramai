"""
Veille Concurrentielle - Le coeur du produit.
Dashboard et alertes pour surveiller la concurrence.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import uuid
import json

from database import get_db, Advertiser, Competitor, AppData, InstagramData, TikTokData, YouTubeData, Ad, User, AdvertiserCompetitor, UserAdvertiser
from models.schemas import (
    WatchOverview, MarketPosition, KeyMetric, Trend, TrendDirection,
    Alert, AlertsList, AlertType, AlertSeverity, Channel,
    Rankings, ChannelRanking, RankingEntry,
)
from core.trends import calculate_trend
from core.sectors import get_sector_label
from core.auth import get_current_user, get_current_advertiser
from core.utils import get_logo_url
from core.permissions import get_advertiser_competitors, parse_advertiser_header

router = APIRouter()


def _batch_load_latest(db: Session, model, competitor_ids: list, extra_filter=None) -> Dict:
    """Batch-load the latest record per competitor for a given model.

    Returns dict {competitor_id: row}.
    Uses a subquery to find max(recorded_at) per competitor, then fetches those rows.
    """
    if not competitor_ids:
        return {}

    # Subquery: max recorded_at per competitor
    sub = db.query(
        model.competitor_id,
        func.max(model.recorded_at).label("max_at"),
    ).filter(model.competitor_id.in_(competitor_ids))
    if extra_filter is not None:
        sub = sub.filter(extra_filter)
    sub = sub.group_by(model.competitor_id).subquery()

    rows = db.query(model).join(
        sub,
        (model.competitor_id == sub.c.competitor_id) & (model.recorded_at == sub.c.max_at),
    )
    if extra_filter is not None:
        rows = rows.filter(extra_filter)
    rows = rows.all()

    result = {}
    for r in rows:
        result[r.competitor_id] = r
    return result


def _batch_load_week_ago(db: Session, model, competitor_ids: list, week_ago, extra_filter=None) -> Dict:
    """Batch-load the latest record before week_ago per competitor."""
    if not competitor_ids:
        return {}

    sub = db.query(
        model.competitor_id,
        func.max(model.recorded_at).label("max_at"),
    ).filter(
        model.competitor_id.in_(competitor_ids),
        model.recorded_at <= week_ago,
    )
    if extra_filter is not None:
        sub = sub.filter(extra_filter)
    sub = sub.group_by(model.competitor_id).subquery()

    rows = db.query(model).join(
        sub,
        (model.competitor_id == sub.c.competitor_id) & (model.recorded_at == sub.c.max_at),
    )
    if extra_filter is not None:
        rows = rows.filter(extra_filter)
    rows = rows.all()

    result = {}
    for r in rows:
        result[r.competitor_id] = r
    return result


def format_number(value: Optional[float], suffix: str = "") -> str:
    """Formate un nombre pour affichage (1.2M, 45K, etc.)."""
    if value is None:
        return "N/A"
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}M{suffix}"
    if value >= 1_000:
        return f"{value/1_000:.0f}K{suffix}"
    return f"{value:.0f}{suffix}"


def get_brand(db: Session, user: User, advertiser_id: int | None = None) -> Advertiser:
    """Récupère l'enseigne courante via user_advertisers join table."""
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    if not user_adv_ids:
        raise HTTPException(status_code=404, detail="Aucune enseigne configurée")
    query = db.query(Advertiser).filter(Advertiser.is_active == True, Advertiser.id.in_(user_adv_ids))
    if advertiser_id:
        query = query.filter(Advertiser.id == advertiser_id)
    brand = query.first()
    if not brand:
        raise HTTPException(status_code=404, detail="Aucune enseigne configurée")
    return brand


def _get_advertiser_competitors_query(db: Session, adv_id: int):
    """Get competitors linked to an advertiser via join table."""
    return (
        db.query(Competitor)
        .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
        .filter(AdvertiserCompetitor.advertiser_id == adv_id, Competitor.is_active == True)
    )


def calculate_global_score(
    app_rating: Optional[float],
    downloads: Optional[int],
    social_followers: Optional[int]
) -> float:
    """
    Calcule un score composite 0-100.
    Pondération: Apps 40%, Social 40%, Downloads 20%
    """
    score = 0.0

    # Score apps (note sur 5 -> score sur 40)
    if app_rating:
        score += (app_rating / 5.0) * 40

    # Score social (normalisé sur 1M followers max -> score sur 40)
    if social_followers:
        normalized = min(social_followers / 1_000_000, 1.0)
        score += normalized * 40

    # Score downloads (normalisé sur 10M -> score sur 20)
    if downloads:
        normalized = min(downloads / 10_000_000, 1.0)
        score += normalized * 20

    return round(score, 1)


# =============================================================================
# Overview
# =============================================================================

@router.get("/overview")
async def get_watch_overview(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Vue d'ensemble de la veille concurrentielle.

    Affiche:
    - Position de l'enseigne dans le marché
    - KPIs clés avec comparaison au meilleur concurrent
    - Résumé textuel de la situation
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    brand = get_brand(db, user, adv_id)
    if not adv_id:
        adv_id = brand.id
    competitors = _get_advertiser_competitors_query(db, adv_id).all()
    comp_ids = [c.id for c in competitors]

    # Batch-load all latest data (6 queries instead of 5*N)
    ps_map = _batch_load_latest(db, AppData, comp_ids, AppData.store == "playstore")
    as_map = _batch_load_latest(db, AppData, comp_ids, AppData.store == "appstore")
    ig_map = _batch_load_latest(db, InstagramData, comp_ids)
    tt_map = _batch_load_latest(db, TikTokData, comp_ids)
    yt_map = _batch_load_latest(db, YouTubeData, comp_ids)

    # Collecte des données pour tous les acteurs
    actors_data = []

    for comp in competitors:
        playstore = ps_map.get(comp.id)
        appstore = as_map.get(comp.id)
        instagram = ig_map.get(comp.id)
        tiktok = tt_map.get(comp.id)
        youtube = yt_map.get(comp.id)

        # Calculs agrégés
        avg_rating = None
        if playstore and appstore and playstore.rating and appstore.rating:
            avg_rating = (playstore.rating + appstore.rating) / 2
        elif playstore and playstore.rating:
            avg_rating = playstore.rating
        elif appstore and appstore.rating:
            avg_rating = appstore.rating

        total_social = 0
        if instagram and instagram.followers:
            total_social += instagram.followers
        if tiktok and tiktok.followers:
            total_social += tiktok.followers
        if youtube and youtube.subscribers:
            total_social += youtube.subscribers

        downloads = playstore.downloads_numeric if playstore else None

        actors_data.append({
            "id": comp.id,
            "name": comp.name,
            "is_brand": comp.name.lower() == brand.company_name.lower(),
            "app_rating": avg_rating,
            "downloads": downloads,
            "social_followers": total_social if total_social > 0 else None,
            "instagram_followers": instagram.followers if instagram else None,
            "playstore_rating": playstore.rating if playstore else None,
            "playstore_downloads": playstore.downloads if playstore else None,
            "score": calculate_global_score(avg_rating, downloads, total_social if total_social > 0 else None),
        })

    # Tri par score pour le classement
    actors_data.sort(key=lambda x: x["score"], reverse=True)

    # Trouve mon enseigne dans le classement
    my_data = next((a for a in actors_data if a["is_brand"]), None)
    my_rank = next((i + 1 for i, a in enumerate(actors_data) if a["is_brand"]), len(actors_data) + 1)

    # Si l'enseigne n'a pas encore de données
    if not my_data:
        my_data = {
            "name": brand.company_name,
            "is_brand": True,
            "app_rating": None,
            "downloads": None,
            "social_followers": None,
            "score": 0,
        }
        my_rank = len(actors_data) + 1

    # Position marché
    position = MarketPosition(
        global_rank=my_rank,
        total_players=len(actors_data) + (0 if my_data in actors_data else 1),
        global_score=my_data["score"],
        score_trend=None,
    )

    # KPIs clés
    key_metrics = []

    # 1. Note moyenne apps
    ratings = [(a["name"], a["app_rating"]) for a in actors_data if a["app_rating"]]
    ratings.sort(key=lambda x: x[1], reverse=True)
    best_rating = ratings[0] if ratings else (None, None)
    my_rating_rank = next((i + 1 for i, (n, r) in enumerate(ratings) if n == brand.company_name), len(ratings) + 1)

    key_metrics.append(KeyMetric(
        id="app_rating",
        label="Note Apps",
        my_value=my_data.get("app_rating"),
        my_formatted=f"{my_data.get('app_rating', 0):.1f}/5" if my_data.get("app_rating") else "N/A",
        best_competitor=best_rating[0],
        best_value=best_rating[1],
        best_formatted=f"{best_rating[1]:.1f}/5" if best_rating[1] else None,
        my_rank=my_rating_rank,
    ))

    # 2. Followers Instagram
    ig_followers = [(a["name"], a["instagram_followers"]) for a in actors_data if a.get("instagram_followers")]
    ig_followers.sort(key=lambda x: x[1], reverse=True)
    best_ig = ig_followers[0] if ig_followers else (None, None)
    my_ig_rank = next((i + 1 for i, (n, f) in enumerate(ig_followers) if n == brand.company_name), len(ig_followers) + 1)

    key_metrics.append(KeyMetric(
        id="instagram_followers",
        label="Followers Instagram",
        my_value=my_data.get("instagram_followers"),
        my_formatted=format_number(my_data.get("instagram_followers")),
        best_competitor=best_ig[0],
        best_value=best_ig[1],
        best_formatted=format_number(best_ig[1]),
        my_rank=my_ig_rank,
    ))

    # 3. Téléchargements Play Store
    downloads = [(a["name"], a["downloads"], a.get("playstore_downloads", "")) for a in actors_data if a.get("downloads")]
    downloads.sort(key=lambda x: x[1], reverse=True)
    best_dl = downloads[0] if downloads else (None, None, "")
    my_dl_rank = next((i + 1 for i, (n, d, _) in enumerate(downloads) if n == brand.company_name), len(downloads) + 1)

    key_metrics.append(KeyMetric(
        id="playstore_downloads",
        label="Downloads Play Store",
        my_value=my_data.get("downloads"),
        my_formatted=my_data.get("playstore_downloads") or format_number(my_data.get("downloads")),
        best_competitor=best_dl[0],
        best_value=best_dl[1],
        best_formatted=best_dl[2] or format_number(best_dl[1]),
        my_rank=my_dl_rank,
    ))

    # 4. Reach social total
    social = [(a["name"], a["social_followers"]) for a in actors_data if a.get("social_followers")]
    social.sort(key=lambda x: x[1], reverse=True)
    best_social = social[0] if social else (None, None)
    my_social_rank = next((i + 1 for i, (n, s) in enumerate(social) if n == brand.company_name), len(social) + 1)

    key_metrics.append(KeyMetric(
        id="social_reach",
        label="Reach Social Total",
        my_value=my_data.get("social_followers"),
        my_formatted=format_number(my_data.get("social_followers")),
        best_competitor=best_social[0],
        best_value=best_social[1],
        best_formatted=format_number(best_social[1]),
        my_rank=my_social_rank,
    ))

    # Génère le résumé
    summary_parts = []
    if my_rating_rank <= 2:
        summary_parts.append(f"Excellent sur les apps (#{my_rating_rank})")
    elif my_rating_rank > len(ratings) // 2:
        summary_parts.append(f"Apps à améliorer (#{my_rating_rank}/{len(ratings)})")

    if my_ig_rank <= 2 and ig_followers:
        summary_parts.append(f"Leader Instagram (#{my_ig_rank})")
    elif my_ig_rank > len(ig_followers) // 2 and ig_followers:
        summary_parts.append(f"Instagram en retard (#{my_ig_rank}/{len(ig_followers)})")

    summary = ". ".join(summary_parts) if summary_parts else "Commencez par ajouter vos concurrents pour voir votre positionnement."

    # Compte les alertes (simulé pour l'instant)
    alerts_count = 0
    critical_alerts = 0

    return WatchOverview(
        brand_name=brand.company_name,
        sector=get_sector_label(brand.sector),
        last_updated=datetime.utcnow(),
        position=position,
        key_metrics=key_metrics,
        summary=summary,
        alerts_count=alerts_count,
        critical_alerts=critical_alerts,
    )


# =============================================================================
# Dashboard - Aggregated endpoint for frontend
# =============================================================================

@router.get("/dashboard")
async def get_dashboard_data(
    days: int = 7,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Endpoint agrégé pour le dashboard frontend.
    Retourne toutes les données competitors + insights en un seul appel.
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    brand = get_brand(db, user, adv_id)
    if not adv_id:
        adv_id = brand.id
    competitors = _get_advertiser_competitors_query(db, adv_id).all()
    comp_ids = [c.id for c in competitors]

    week_ago = datetime.utcnow() - timedelta(days=days)

    # Batch-load all data (12 queries instead of 10*N)
    ig_latest_map = _batch_load_latest(db, InstagramData, comp_ids)
    ig_old_map = _batch_load_week_ago(db, InstagramData, comp_ids, week_ago)
    tt_latest_map = _batch_load_latest(db, TikTokData, comp_ids)
    tt_old_map = _batch_load_week_ago(db, TikTokData, comp_ids, week_ago)
    yt_latest_map = _batch_load_latest(db, YouTubeData, comp_ids)
    yt_old_map = _batch_load_week_ago(db, YouTubeData, comp_ids, week_ago)
    ps_latest_map = _batch_load_latest(db, AppData, comp_ids, AppData.store == "playstore")
    as_latest_map = _batch_load_latest(db, AppData, comp_ids, AppData.store == "appstore")

    # Snapchat ads: batch-load counts + impressions per competitor
    snap_data_map = {}
    if comp_ids:
        snap_rows = db.query(
            Ad.competitor_id,
            func.count(Ad.id).label("cnt"),
            func.coalesce(func.sum(Ad.impressions_min), 0).label("imp"),
        ).filter(
            Ad.competitor_id.in_(comp_ids),
            Ad.platform == "snapchat",
        ).group_by(Ad.competitor_id).all()
        for row in snap_rows:
            snap_data_map[row.competitor_id] = {
                "ads_count": row.cnt,
                "total_impressions": row.imp,
            }

    # Build entity_name lookup for snap
    snap_entity_map = {c.id: c.snapchat_entity_name for c in competitors if c.snapchat_entity_name}

    competitor_data = []

    for comp in competitors:
        # Instagram
        ig_latest = ig_latest_map.get(comp.id)
        ig_old = ig_old_map.get(comp.id)

        ig_data = None
        if ig_latest and ig_latest.followers:
            ig_growth = 0
            if ig_old and ig_old.followers and ig_old.followers > 0:
                ig_growth = round(((ig_latest.followers - ig_old.followers) / ig_old.followers) * 100, 2)
            ig_data = {
                "followers": ig_latest.followers,
                "growth_7d": ig_growth,
                "engagement_rate": round(ig_latest.engagement_rate or 0, 2),
                "posts": ig_latest.posts_count or 0,
            }

        # TikTok
        tt_latest = tt_latest_map.get(comp.id)
        tt_old = tt_old_map.get(comp.id)

        tt_data = None
        if tt_latest and tt_latest.followers:
            tt_growth = 0
            if tt_old and tt_old.followers and tt_old.followers > 0:
                tt_growth = round(((tt_latest.followers - tt_old.followers) / tt_old.followers) * 100, 2)
            tt_data = {
                "followers": tt_latest.followers,
                "growth_7d": tt_growth,
                "likes": tt_latest.likes or 0,
                "videos": tt_latest.videos_count or 0,
            }

        # YouTube
        yt_latest = yt_latest_map.get(comp.id)
        yt_old = yt_old_map.get(comp.id)

        yt_data = None
        if yt_latest and yt_latest.subscribers:
            yt_growth = 0
            if yt_old and yt_old.subscribers and yt_old.subscribers > 0:
                yt_growth = round(((yt_latest.subscribers - yt_old.subscribers) / yt_old.subscribers) * 100, 2)
            yt_data = {
                "subscribers": yt_latest.subscribers,
                "growth_7d": yt_growth,
                "views": yt_latest.total_views or 0,
                "videos": yt_latest.videos_count or 0,
            }

        # Play Store
        ps_latest = ps_latest_map.get(comp.id)
        ps_data = None
        if ps_latest:
            ps_data = {
                "app_name": ps_latest.app_name,
                "rating": round(ps_latest.rating, 2) if ps_latest.rating else None,
                "reviews": ps_latest.reviews_count,
                "downloads": ps_latest.downloads,
                "version": ps_latest.version,
            }

        # App Store
        as_latest = as_latest_map.get(comp.id)
        as_data = None
        if as_latest:
            as_data = {
                "app_name": as_latest.app_name,
                "rating": round(as_latest.rating, 2) if as_latest.rating else None,
                "reviews": as_latest.reviews_count,
                "version": as_latest.version,
            }

        # Total social
        total_social = 0
        if ig_data:
            total_social += ig_data["followers"]
        if tt_data:
            total_social += tt_data["followers"]
        if yt_data:
            total_social += yt_data["subscribers"]

        # Average app rating
        ratings = []
        if ps_data and ps_data["rating"]:
            ratings.append(ps_data["rating"])
        if as_data and as_data["rating"]:
            ratings.append(as_data["rating"])
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

        score = calculate_global_score(
            avg_rating,
            ps_latest.downloads_numeric if ps_latest else None,
            total_social if total_social > 0 else None,
        )

        # Snapchat
        snap_raw = snap_data_map.get(comp.id)
        snap_data = None
        if snap_raw and snap_raw["ads_count"] > 0:
            snap_data = {
                "ads_count": snap_raw["ads_count"],
                "total_impressions": snap_raw["total_impressions"],
                "entity_name": snap_entity_map.get(comp.id),
            }

        competitor_data.append({
            "id": comp.id,
            "name": comp.name,
            "logo_url": get_logo_url(comp.website),
            "score": score,
            "rank": 0,
            "instagram": ig_data,
            "tiktok": tt_data,
            "youtube": yt_data,
            "playstore": ps_data,
            "appstore": as_data,
            "snapchat": snap_data,
            "total_social": total_social,
            "avg_app_rating": avg_rating,
        })

    # Sort by score and assign ranks
    competitor_data.sort(key=lambda x: x["score"], reverse=True)
    for i, c in enumerate(competitor_data):
        c["rank"] = i + 1

    # Generate insights
    insights = _generate_insights(competitor_data)

    # Platform leaders
    platform_leaders = _get_platform_leaders(competitor_data)

    # Separate brand from competitors
    brand_data = None
    competitors_only = []
    for c in competitor_data:
        if c["name"].lower() == brand.company_name.lower():
            brand_data = c
        else:
            competitors_only.append(c)

    # Re-rank competitors without brand
    for i, c in enumerate(competitors_only):
        c["rank"] = i + 1

    # If brand not found among competitors, build minimal brand_data from Advertiser
    if not brand_data:
        brand_data = {
            "id": brand.id,
            "name": brand.company_name,
            "logo_url": get_logo_url(brand.website),
            "score": 0,
            "rank": len(competitor_data) + 1,
            "rank_among_all": len(competitor_data) + 1,
            "total_players": len(competitor_data) + 1,
            "instagram": None,
            "tiktok": None,
            "youtube": None,
            "playstore": None,
            "appstore": None,
            "snapchat": None,
            "total_social": 0,
            "avg_app_rating": None,
        }

    # Compute brand rank among all (brand included)
    if brand_data and "rank_among_all" not in brand_data:
        brand_data["rank_among_all"] = brand_data["rank"]
        brand_data["total_players"] = len(competitor_data)

    # Ad intelligence
    ad_intelligence = _build_ad_intelligence(db, competitor_data, brand.company_name)

    # Multi-dimensional rankings
    rankings = _build_rankings(competitor_data, brand.company_name)

    # Compute real freshness from loaded data
    all_timestamps = []
    freshness = {}
    for label, data_map in [
        ("instagram", ig_latest_map), ("tiktok", tt_latest_map),
        ("youtube", yt_latest_map), ("playstore", ps_latest_map),
        ("appstore", as_latest_map),
    ]:
        ts_list = [row.recorded_at for row in data_map.values() if row and row.recorded_at]
        if ts_list:
            max_ts = max(ts_list)
            freshness[label] = max_ts.isoformat()
            all_timestamps.append(max_ts)
        else:
            freshness[label] = None

    last_updated = max(all_timestamps).isoformat() if all_timestamps else datetime.utcnow().isoformat()

    return {
        "brand_name": brand.company_name,
        "sector": get_sector_label(brand.sector),
        "last_updated": last_updated,
        "freshness": freshness,
        "brand": brand_data,
        "competitors": competitors_only,
        "insights": insights,
        "platform_leaders": platform_leaders,
        "ad_intelligence": ad_intelligence,
        "rankings": rankings,
    }


def _generate_insights(competitors: list) -> list:
    """Generate smart insights from competitor data."""
    insights = []

    # Find leaders per platform
    ig_sorted = sorted(
        [c for c in competitors if c["instagram"]],
        key=lambda x: x["instagram"]["followers"],
        reverse=True,
    )
    tt_sorted = sorted(
        [c for c in competitors if c["tiktok"]],
        key=lambda x: x["tiktok"]["followers"],
        reverse=True,
    )
    yt_sorted = sorted(
        [c for c in competitors if c["youtube"]],
        key=lambda x: x["youtube"]["subscribers"],
        reverse=True,
    )

    # Leader insights
    if ig_sorted:
        leader = ig_sorted[0]
        insights.append({
            "type": "leader",
            "icon": "crown",
            "text": f"{leader['name']} domine Instagram avec {format_number(leader['instagram']['followers'])} followers",
            "severity": "info",
        })

    if tt_sorted:
        leader = tt_sorted[0]
        insights.append({
            "type": "leader",
            "icon": "crown",
            "text": f"{leader['name']} est leader TikTok avec {format_number(leader['tiktok']['followers'])} followers",
            "severity": "info",
        })

    # Growth insights
    growth_data = []
    for c in competitors:
        if c["instagram"] and c["instagram"]["growth_7d"] != 0:
            growth_data.append((c["name"], "Instagram", c["instagram"]["growth_7d"]))
        if c["tiktok"] and c["tiktok"]["growth_7d"] != 0:
            growth_data.append((c["name"], "TikTok", c["tiktok"]["growth_7d"]))
        if c["youtube"] and c["youtube"]["growth_7d"] != 0:
            growth_data.append((c["name"], "YouTube", c["youtube"]["growth_7d"]))

    if growth_data:
        best_growth = max(growth_data, key=lambda x: x[2])
        if best_growth[2] > 0:
            insights.append({
                "type": "growth",
                "icon": "trending-up",
                "text": f"{best_growth[0]} affiche la plus forte croissance {best_growth[1]} (+{best_growth[2]:.1f}%/sem)",
                "severity": "success",
            })

    # App rating insights
    rated = [c for c in competitors if c["avg_app_rating"]]
    if rated:
        best_app = max(rated, key=lambda x: x["avg_app_rating"])
        worst_app = min(rated, key=lambda x: x["avg_app_rating"])
        if best_app["name"] != worst_app["name"]:
            diff = best_app["avg_app_rating"] - worst_app["avg_app_rating"]
            insights.append({
                "type": "app",
                "icon": "star",
                "text": f"{best_app['name']} a la meilleure note app ({best_app['avg_app_rating']:.1f}/5), {worst_app['name']} est en retard ({worst_app['avg_app_rating']:.1f}/5)",
                "severity": "info",
            })

    # Engagement insights
    engagement_data = [(c["name"], c["instagram"]["engagement_rate"]) for c in competitors if c["instagram"] and c["instagram"]["engagement_rate"] > 0]
    if engagement_data:
        best_eng = max(engagement_data, key=lambda x: x[1])
        insights.append({
            "type": "engagement",
            "icon": "heart",
            "text": f"{best_eng[0]} a le meilleur engagement Instagram ({best_eng[1]:.1f}%)",
            "severity": "info",
        })

    # Weakness detection
    for c in competitors:
        if c["total_social"] < 1000 and (c["instagram"] or c["tiktok"] or c["youtube"]):
            insights.append({
                "type": "alert",
                "icon": "alert-triangle",
                "text": f"{c['name']} est quasi-absent des reseaux sociaux ({format_number(c['total_social'])} reach total)",
                "severity": "warning",
            })

    return insights


def _get_platform_leaders(competitors: list) -> dict:
    """Get the leader for each platform."""
    leaders = {}

    # Instagram
    ig = [c for c in competitors if c["instagram"]]
    if ig:
        leader = max(ig, key=lambda x: x["instagram"]["followers"])
        leaders["instagram"] = {"leader": leader["name"], "value": leader["instagram"]["followers"], "logo_url": leader.get("logo_url")}

    # TikTok
    tt = [c for c in competitors if c["tiktok"]]
    if tt:
        leader = max(tt, key=lambda x: x["tiktok"]["followers"])
        leaders["tiktok"] = {"leader": leader["name"], "value": leader["tiktok"]["followers"], "logo_url": leader.get("logo_url")}

    # YouTube
    yt = [c for c in competitors if c["youtube"]]
    if yt:
        leader = max(yt, key=lambda x: x["youtube"]["subscribers"])
        leaders["youtube"] = {"leader": leader["name"], "value": leader["youtube"]["subscribers"], "logo_url": leader.get("logo_url")}

    # Play Store
    ps = [c for c in competitors if c["playstore"] and c["playstore"]["rating"]]
    if ps:
        leader = max(ps, key=lambda x: x["playstore"]["rating"])
        leaders["playstore"] = {"leader": leader["name"], "value": leader["playstore"]["rating"], "logo_url": leader.get("logo_url")}

    # App Store
    aps = [c for c in competitors if c["appstore"] and c["appstore"]["rating"]]
    if aps:
        leader = max(aps, key=lambda x: x["appstore"]["rating"])
        leaders["appstore"] = {"leader": leader["name"], "value": leader["appstore"]["rating"], "logo_url": leader.get("logo_url")}

    # Snapchat (by ads count)
    snap = [c for c in competitors if c.get("snapchat") and c["snapchat"]["ads_count"] > 0]
    if snap:
        leader = max(snap, key=lambda x: x["snapchat"]["ads_count"])
        leaders["snapchat"] = {"leader": leader["name"], "value": leader["snapchat"]["ads_count"], "logo_url": leader.get("logo_url")}

    return leaders


def _build_ad_intelligence(db: Session, competitor_data: list, brand_name: str) -> dict:
    """Build ad intelligence: format breakdown, platform mix, payer/advertiser analysis."""
    # Only load ads for tracked competitors to limit memory usage
    tracked_ids = [c["id"] for c in competitor_data]
    all_ads = db.query(Ad).filter(Ad.competitor_id.in_(tracked_ids)).all() if tracked_ids else []

    # Per competitor ad data
    comp_ads = {}
    for ad in all_ads:
        cid = ad.competitor_id
        if cid not in comp_ads:
            comp_ads[cid] = []
        comp_ads[cid].append(ad)

    # Global format breakdown
    format_counts = {}
    platform_counts = {}
    advertisers = {}  # page_name -> {ads, competitors, active, formats}
    payers = {}  # byline/disclaimer -> {total, active, pages} (only explicit payer data)

    for ad in all_ads:
        fmt = ad.display_format or "AUTRE"
        format_counts[fmt] = format_counts.get(fmt, 0) + 1

        try:
            pps = json.loads(ad.publisher_platforms) if ad.publisher_platforms else []
        except (json.JSONDecodeError, TypeError):
            pps = []
        # Fallback: use ad.platform for ads without publisher_platforms (e.g. Google Ads)
        if not pps and ad.platform:
            pps = [ad.platform.upper()]
        for pp in pps:
            platform_counts[pp] = platform_counts.get(pp, 0) + 1

        pname = ad.page_name or "Inconnu"
        if pname not in advertisers:
            advertisers[pname] = {"total": 0, "active": 0, "competitor_id": ad.competitor_id, "formats": {}}
        advertisers[pname]["total"] += 1
        if ad.is_active:
            advertisers[pname]["active"] += 1
        fmt_key = ad.display_format or "AUTRE"
        advertisers[pname]["formats"][fmt_key] = advertisers[pname]["formats"].get(fmt_key, 0) + 1

        # Payer tracking: only use REAL payer data (byline/disclaimer_label)
        # Don't fallback to page_name — that's the advertiser, not the payer
        explicit_payer = ad.byline or ad.disclaimer_label
        if explicit_payer:
            if explicit_payer not in payers:
                payers[explicit_payer] = {"total": 0, "active": 0, "pages": set()}
            payers[explicit_payer]["total"] += 1
            if ad.is_active:
                payers[explicit_payer]["active"] += 1
            payers[explicit_payer]["pages"].add(pname)

    # Per competitor summary
    competitor_ad_summary = []
    for cd in competitor_data:
        cid = cd["id"]
        ads = comp_ads.get(cid, [])
        active = [a for a in ads if a.is_active]

        # Format breakdown for this competitor
        comp_formats = {}
        comp_platforms = set()
        for a in ads:
            f = a.display_format or "AUTRE"
            comp_formats[f] = comp_formats.get(f, 0) + 1
            try:
                pps = json.loads(a.publisher_platforms) if a.publisher_platforms else []
            except (json.JSONDecodeError, TypeError):
                pps = []
            if not pps and a.platform:
                pps = [a.platform.upper()]
            for pp in pps:
                comp_platforms.add(pp)

        # Estimated spend (priority: declared > impressions x CPM > reach x CPM)
        spend_min = 0
        spend_max = 0
        for a in ads:
            if a.estimated_spend_min and a.estimated_spend_min > 0:
                spend_min += a.estimated_spend_min
                spend_max += a.estimated_spend_max or a.estimated_spend_min
            elif a.impressions_min and a.impressions_min > 0:
                cpm = 3.0  # Default CPM for Meta FR
                spend_min += (a.impressions_min / 1000) * cpm
                spend_max += ((a.impressions_max or a.impressions_min) / 1000) * cpm
            elif a.eu_total_reach and a.eu_total_reach > 100:
                cpm = 3.0
                spend_min += (a.eu_total_reach / 1000) * cpm * 0.7
                spend_max += (a.eu_total_reach / 1000) * cpm * 1.3

        competitor_ad_summary.append({
            "id": cid,
            "name": cd["name"],
            "logo_url": cd.get("logo_url"),
            "is_brand": cd["name"].lower() == brand_name.lower(),
            "total_ads": len(ads),
            "active_ads": len(active),
            "formats": comp_formats,
            "platforms": sorted(comp_platforms),
            "estimated_spend_min": spend_min,
            "estimated_spend_max": spend_max,
        })

    competitor_ad_summary.sort(key=lambda x: x["total_ads"], reverse=True)

    # Format labels for display
    FORMAT_LABELS = {
        "VIDEO": "Video",
        "IMAGE": "Image statique",
        "DPA": "Dynamic Product Ads",
        "DCO": "Dynamic Creative",
        "CAROUSEL": "Carrousel",
        "AUTRE": "Autre",
    }

    # Recommendations based on competitor activity
    recommendations = _generate_ad_recommendations(
        competitor_ad_summary, format_counts, platform_counts, brand_name
    )

    total_spend_min = 0
    total_spend_max = 0
    for a in all_ads:
        if a.estimated_spend_min and a.estimated_spend_min > 0:
            total_spend_min += a.estimated_spend_min
            total_spend_max += a.estimated_spend_max or a.estimated_spend_min
        elif a.impressions_min and a.impressions_min > 0:
            cpm = 3.0
            total_spend_min += (a.impressions_min / 1000) * cpm
            total_spend_max += ((a.impressions_max or a.impressions_min) / 1000) * cpm
        elif a.eu_total_reach and a.eu_total_reach > 100:
            cpm = 3.0
            total_spend_min += (a.eu_total_reach / 1000) * cpm * 0.7
            total_spend_max += (a.eu_total_reach / 1000) * cpm * 1.3

    return {
        "total_ads": len(all_ads),
        "total_active": len([a for a in all_ads if a.is_active]),
        "total_estimated_spend": {"min": total_spend_min, "max": total_spend_max},
        "format_breakdown": [
            {"format": k, "label": FORMAT_LABELS.get(k, k), "count": v,
             "pct": round(v / len(all_ads) * 100, 1) if all_ads else 0}
            for k, v in sorted(format_counts.items(), key=lambda x: -x[1])
        ],
        "platform_breakdown": [
            {"platform": k, "count": v,
             "pct": round(v / len(all_ads) * 100, 1) if all_ads else 0}
            for k, v in sorted(platform_counts.items(), key=lambda x: -x[1])
        ],
        "advertisers": [
            {"name": k, "total": v["total"], "active": v["active"],
             "top_format": max(v["formats"], key=v["formats"].get) if v["formats"] else None}
            for k, v in sorted(advertisers.items(), key=lambda x: -x[1]["total"])
        ],
        "payers": [
            {"name": k, "total": v["total"], "active": v["active"],
             "pages": sorted(v["pages"])}
            for k, v in sorted(payers.items(), key=lambda x: -x[1]["total"])
        ],
        "competitor_summary": competitor_ad_summary,
        "recommendations": recommendations,
    }


def _generate_ad_recommendations(comp_summary: list, format_counts: dict,
                                  platform_counts: dict, brand_name: str) -> list:
    """Generate actionable ad recommendations based on competitor behavior."""
    recs = []
    total_ads = sum(format_counts.values()) or 1

    # Find brand data
    brand_ads = next((c for c in comp_summary if c["is_brand"]), None)
    competitors_only = [c for c in comp_summary if not c["is_brand"]]

    # Formats competitors use that brand doesn't
    brand_formats = set(brand_ads["formats"].keys()) if brand_ads else set()
    competitor_formats = set()
    for c in competitors_only:
        competitor_formats.update(c["formats"].keys())

    FORMAT_LABELS = {
        "VIDEO": "Video",
        "IMAGE": "Image",
        "DPA": "Dynamic Product Ads",
        "DCO": "Dynamic Creative",
        "CAROUSEL": "Carrousel",
    }

    missing_formats = competitor_formats - brand_formats
    for fmt in missing_formats:
        users = [c["name"] for c in competitors_only if fmt in c["formats"]]
        count = format_counts.get(fmt, 0)
        pct = round(count / total_ads * 100)
        if pct >= 5:  # Only recommend if >=5% of total ads
            recs.append({
                "type": "format",
                "priority": "high" if pct >= 20 else "medium",
                "format": fmt,
                "label": FORMAT_LABELS.get(fmt, fmt),
                "text": f"Activez le format {FORMAT_LABELS.get(fmt, fmt)} — {pct}% des pubs concurrentes, utilisé par {', '.join(users)}",
                "used_by": users,
                "market_share_pct": pct,
            })

    # Top format the brand should double down on
    if brand_ads and brand_ads["formats"]:
        top_brand_fmt = max(brand_ads["formats"], key=brand_ads["formats"].get)
        fmt_total = format_counts.get(top_brand_fmt, 0)
        pct = round(fmt_total / total_ads * 100)
        recs.append({
            "type": "strength",
            "priority": "info",
            "format": top_brand_fmt,
            "label": FORMAT_LABELS.get(top_brand_fmt, top_brand_fmt),
            "text": f"Continuez le {FORMAT_LABELS.get(top_brand_fmt, top_brand_fmt)} — votre format principal, {pct}% du marché",
            "market_share_pct": pct,
        })

    # Platform recommendations
    brand_platforms = set(brand_ads["platforms"]) if brand_ads else set()
    all_platforms = set()
    for c in competitors_only:
        all_platforms.update(c["platforms"])

    missing_platforms = all_platforms - brand_platforms
    for plat in missing_platforms:
        count = platform_counts.get(plat, 0)
        pct = round(count / total_ads * 100)
        if pct >= 10:
            recs.append({
                "type": "platform",
                "priority": "medium",
                "format": plat,
                "label": plat.title(),
                "text": f"Etendez sur {plat.title()} — {pct}% des diffusions concurrentes y sont présentes",
                "market_share_pct": pct,
            })

    # Ad volume comparison
    if brand_ads:
        avg_competitor_ads = sum(c["total_ads"] for c in competitors_only) / len(competitors_only) if competitors_only else 0
        if brand_ads["total_ads"] < avg_competitor_ads * 0.5 and avg_competitor_ads > 5:
            recs.append({
                "type": "volume",
                "priority": "high",
                "format": "all",
                "label": "Volume",
                "text": f"Augmentez votre volume — vous avez {brand_ads['total_ads']} pubs vs {avg_competitor_ads:.0f} en moyenne chez les concurrents",
                "market_share_pct": round(brand_ads["total_ads"] / avg_competitor_ads * 100) if avg_competitor_ads else 0,
            })
    elif competitors_only:
        avg_ads = sum(c["total_ads"] for c in competitors_only) / len(competitors_only)
        if avg_ads > 0:
            recs.append({
                "type": "volume",
                "priority": "high",
                "format": "all",
                "label": "Volume",
                "text": f"Lancez vos campagnes — vos concurrents ont en moyenne {avg_ads:.0f} publicités actives",
                "market_share_pct": 0,
            })

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "info": 2}
    recs.sort(key=lambda x: priority_order.get(x["priority"], 3))

    return recs


def _build_rankings(competitor_data: list, brand_name: str) -> list:
    """Build multi-dimensional rankings for competitors."""
    rankings = []

    # 1. Social Reach ranking
    social_ranked = sorted(
        [c for c in competitor_data if c["total_social"] > 0],
        key=lambda x: x["total_social"], reverse=True
    )
    if social_ranked:
        rankings.append({
            "id": "social_reach",
            "label": "Reach Social Total",
            "icon": "users",
            "entries": [{
                "rank": i + 1,
                "name": c["name"],
                "logo_url": c.get("logo_url"),
                "value": c["total_social"],
                "formatted": format_number(c["total_social"]),
                "is_brand": c["name"].lower() == brand_name.lower(),
            } for i, c in enumerate(social_ranked)],
        })

    # 2. Instagram ranking
    ig_ranked = sorted(
        [c for c in competitor_data if c["instagram"]],
        key=lambda x: x["instagram"]["followers"], reverse=True
    )
    if ig_ranked:
        rankings.append({
            "id": "instagram",
            "label": "Instagram Followers",
            "icon": "instagram",
            "entries": [{
                "rank": i + 1,
                "name": c["name"],
                "logo_url": c.get("logo_url"),
                "value": c["instagram"]["followers"],
                "formatted": format_number(c["instagram"]["followers"]),
                "is_brand": c["name"].lower() == brand_name.lower(),
                "extra": f"{c['instagram']['engagement_rate']:.1f}% eng." if c["instagram"].get("engagement_rate") else None,
            } for i, c in enumerate(ig_ranked)],
        })

    # 3. TikTok ranking
    tt_ranked = sorted(
        [c for c in competitor_data if c["tiktok"] and c["tiktok"]["followers"] > 0],
        key=lambda x: x["tiktok"]["followers"], reverse=True
    )
    if tt_ranked:
        rankings.append({
            "id": "tiktok",
            "label": "TikTok Followers",
            "icon": "music",
            "entries": [{
                "rank": i + 1,
                "name": c["name"],
                "logo_url": c.get("logo_url"),
                "value": c["tiktok"]["followers"],
                "formatted": format_number(c["tiktok"]["followers"]),
                "is_brand": c["name"].lower() == brand_name.lower(),
                "extra": f"{format_number(c['tiktok']['likes'])} likes" if c["tiktok"].get("likes") else None,
            } for i, c in enumerate(tt_ranked)],
        })

    # 4. YouTube ranking
    yt_ranked = sorted(
        [c for c in competitor_data if c["youtube"]],
        key=lambda x: x["youtube"]["subscribers"], reverse=True
    )
    if yt_ranked:
        rankings.append({
            "id": "youtube",
            "label": "YouTube Abonnés",
            "icon": "youtube",
            "entries": [{
                "rank": i + 1,
                "name": c["name"],
                "logo_url": c.get("logo_url"),
                "value": c["youtube"]["subscribers"],
                "formatted": format_number(c["youtube"]["subscribers"]),
                "is_brand": c["name"].lower() == brand_name.lower(),
                "extra": f"{format_number(c['youtube']['views'])} vues" if c["youtube"].get("views") else None,
            } for i, c in enumerate(yt_ranked)],
        })

    # 5. Snapchat Ads ranking
    snap_ranked = sorted(
        [c for c in competitor_data if c.get("snapchat") and c["snapchat"]["ads_count"] > 0],
        key=lambda x: x["snapchat"]["ads_count"], reverse=True
    )
    if snap_ranked:
        rankings.append({
            "id": "snapchat",
            "label": "Snapchat Ads",
            "icon": "ghost",
            "entries": [{
                "rank": i + 1,
                "name": c["name"],
                "logo_url": c.get("logo_url"),
                "value": c["snapchat"]["ads_count"],
                "formatted": f"{c['snapchat']['ads_count']} pubs",
                "is_brand": c["name"].lower() == brand_name.lower(),
                "extra": f"{format_number(c['snapchat']['total_impressions'])} imp." if c["snapchat"].get("total_impressions") else None,
            } for i, c in enumerate(snap_ranked)],
        })

    # 6. App rating ranking (avg of both stores)
    app_ranked = sorted(
        [c for c in competitor_data if c["avg_app_rating"]],
        key=lambda x: x["avg_app_rating"], reverse=True
    )
    if app_ranked:
        rankings.append({
            "id": "app_rating",
            "label": "Note Apps (moyenne)",
            "icon": "star",
            "entries": [{
                "rank": i + 1,
                "name": c["name"],
                "logo_url": c.get("logo_url"),
                "value": c["avg_app_rating"],
                "formatted": f"{c['avg_app_rating']:.2f}/5",
                "is_brand": c["name"].lower() == brand_name.lower(),
            } for i, c in enumerate(app_ranked)],
        })

    # 6. Engagement ranking (Instagram)
    eng_ranked = sorted(
        [c for c in competitor_data if c["instagram"] and c["instagram"].get("engagement_rate", 0) > 0],
        key=lambda x: x["instagram"]["engagement_rate"], reverse=True
    )
    if eng_ranked:
        rankings.append({
            "id": "engagement",
            "label": "Engagement Instagram",
            "icon": "heart",
            "entries": [{
                "rank": i + 1,
                "name": c["name"],
                "logo_url": c.get("logo_url"),
                "value": c["instagram"]["engagement_rate"],
                "formatted": f"{c['instagram']['engagement_rate']:.1f}%",
                "is_brand": c["name"].lower() == brand_name.lower(),
            } for i, c in enumerate(eng_ranked)],
        })

    # 7. Score global ranking
    score_ranked = sorted(competitor_data, key=lambda x: x["score"], reverse=True)
    rankings.insert(0, {
        "id": "global_score",
        "label": "Score Global",
        "icon": "trophy",
        "entries": [{
            "rank": i + 1,
            "name": c["name"],
            "logo_url": c.get("logo_url"),
            "value": c["score"],
            "formatted": f"{c['score']:.0f}/100",
            "is_brand": c["name"].lower() == brand_name.lower(),
        } for i, c in enumerate(score_ranked)],
    })

    return rankings


# =============================================================================
# Alerts
# =============================================================================

@router.get("/alerts")
async def get_alerts(
    limit: int = 20,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Liste les alertes de veille concurrentielle.

    Types d'alertes:
    - rating_change: Changement significatif de note
    - follower_spike: Pic de followers
    - app_update: Mise à jour d'app
    - new_ad: Nouvelle publicité détectée
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    brand = get_brand(db, user, adv_id)
    if not adv_id:
        adv_id = brand.id
    alerts = []

    # Build competitor name lookup (scoped via join table)
    all_comps = _get_advertiser_competitors_query(db, adv_id).all()
    comp_names = {c.id: c.name for c in all_comps}

    # Génère des alertes basées sur les données récentes
    week_ago = datetime.utcnow() - timedelta(days=7)
    comp_ids = [c.id for c in all_comps]

    # Alertes sur les mises à jour d'apps
    app_query = db.query(AppData).filter(AppData.recorded_at >= week_ago)
    if comp_ids:
        app_query = app_query.filter(AppData.competitor_id.in_(comp_ids))
    recent_apps = app_query.order_by(desc(AppData.recorded_at)).limit(10).all()

    for app in recent_apps:
        name = comp_names.get(app.competitor_id)
        if not name:
            continue

        alerts.append(Alert(
            id=str(uuid.uuid4())[:8],
            type=AlertType.APP_UPDATE,
            severity=AlertSeverity.INFO,
            title=f"{name} - Données app mises à jour",
            description=f"Note: {app.rating}/5, {app.reviews_count} avis ({app.store})",
            competitor_name=name,
            channel=Channel.PLAYSTORE if app.store == "playstore" else Channel.APPSTORE,
            detected_at=app.recorded_at,
            is_read=False,
        ))

    # Alertes sur les données Instagram
    ig_query = db.query(InstagramData).filter(InstagramData.recorded_at >= week_ago)
    if comp_ids:
        ig_query = ig_query.filter(InstagramData.competitor_id.in_(comp_ids))
    recent_ig = ig_query.order_by(desc(InstagramData.recorded_at)).limit(5).all()

    for ig in recent_ig:
        name = comp_names.get(ig.competitor_id)
        if not name:
            continue

        alerts.append(Alert(
            id=str(uuid.uuid4())[:8],
            type=AlertType.FOLLOWER_SPIKE,
            severity=AlertSeverity.INFO,
            title=f"{name} - Données Instagram",
            description=f"{ig.followers:,} followers, engagement {ig.engagement_rate or 0:.1f}%",
            competitor_name=name,
            channel=Channel.INSTAGRAM,
            detected_at=ig.recorded_at,
            is_read=False,
        ))

    # Tri par date
    alerts.sort(key=lambda x: x.detected_at, reverse=True)
    alerts = alerts[:limit]

    return AlertsList(
        total=len(alerts),
        unread=len([a for a in alerts if not a.is_read]),
        critical=len([a for a in alerts if a.severity == AlertSeverity.CRITICAL]),
        alerts=alerts,
    )


# =============================================================================
# Rankings
# =============================================================================

@router.get("/rankings")
async def get_rankings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Classements par canal.

    Retourne le leaderboard pour chaque métrique clé.
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    brand = get_brand(db, user, adv_id)
    if not adv_id:
        adv_id = brand.id
    competitors = _get_advertiser_competitors_query(db, adv_id).all()
    comp_ids = [c.id for c in competitors]
    rankings = []

    # Batch-load all latest data (3 queries instead of 3*N)
    ps_map = _batch_load_latest(db, AppData, comp_ids, AppData.store == "playstore")
    ig_map = _batch_load_latest(db, InstagramData, comp_ids)
    tt_map = _batch_load_latest(db, TikTokData, comp_ids)

    # Ranking Play Store (note)
    playstore_data = []
    for comp in competitors:
        app = ps_map.get(comp.id)
        if app and app.rating:
            playstore_data.append({
                "name": comp.name,
                "value": app.rating,
                "is_brand": comp.name.lower() == brand.company_name.lower(),
            })

    playstore_data.sort(key=lambda x: x["value"], reverse=True)
    my_ps_rank = next((i + 1 for i, d in enumerate(playstore_data) if d["is_brand"]), 0)

    rankings.append(ChannelRanking(
        channel="playstore",
        channel_label="Play Store",
        metric="rating",
        metric_label="Note moyenne",
        my_rank=my_ps_rank,
        total=len(playstore_data),
        leaderboard=[
            RankingEntry(
                rank=i + 1,
                competitor_name=d["name"],
                value=d["value"],
                formatted_value=f"{d['value']:.2f}/5",
                is_my_brand=d["is_brand"],
            )
            for i, d in enumerate(playstore_data[:10])
        ],
    ))

    # Ranking Instagram (followers)
    instagram_data = []
    for comp in competitors:
        ig = ig_map.get(comp.id)
        if ig and ig.followers:
            instagram_data.append({
                "name": comp.name,
                "value": ig.followers,
                "is_brand": comp.name.lower() == brand.company_name.lower(),
            })

    instagram_data.sort(key=lambda x: x["value"], reverse=True)
    my_ig_rank = next((i + 1 for i, d in enumerate(instagram_data) if d["is_brand"]), 0)

    rankings.append(ChannelRanking(
        channel="instagram",
        channel_label="Instagram",
        metric="followers",
        metric_label="Followers",
        my_rank=my_ig_rank,
        total=len(instagram_data),
        leaderboard=[
            RankingEntry(
                rank=i + 1,
                competitor_name=d["name"],
                value=d["value"],
                formatted_value=format_number(d["value"]),
                is_my_brand=d["is_brand"],
            )
            for i, d in enumerate(instagram_data[:10])
        ],
    ))

    # Ranking TikTok (followers)
    tiktok_data = []
    for comp in competitors:
        tt = tt_map.get(comp.id)
        if tt and tt.followers:
            tiktok_data.append({
                "name": comp.name,
                "value": tt.followers,
                "is_brand": comp.name.lower() == brand.company_name.lower(),
            })

    tiktok_data.sort(key=lambda x: x["value"], reverse=True)
    my_tt_rank = next((i + 1 for i, d in enumerate(tiktok_data) if d["is_brand"]), 0)

    if tiktok_data:
        rankings.append(ChannelRanking(
            channel="tiktok",
            channel_label="TikTok",
            metric="followers",
            metric_label="Followers",
            my_rank=my_tt_rank,
            total=len(tiktok_data),
            leaderboard=[
                RankingEntry(
                    rank=i + 1,
                    competitor_name=d["name"],
                    value=d["value"],
                    formatted_value=format_number(d["value"]),
                    is_my_brand=d["is_brand"],
                )
                for i, d in enumerate(tiktok_data[:10])
            ],
        ))

    return Rankings(
        updated_at=datetime.utcnow(),
        rankings=rankings,
    )

"""
Admin backoffice router.
Platform stats accessible to all authenticated users (scoped to their data).
User management restricted to admins.
"""
import json
import math
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from database import (
    get_db, engine, User, Advertiser, Competitor,
    Ad, InstagramData, TikTokData, YouTubeData, AppData, StoreLocation,
    PromptTemplate, Store, AdvertiserCompetitor,
    deduplicate_competitors,
)
from core.auth import get_current_user
from core.sectors import SECTORS, list_sectors
from services.scheduler import scheduler

router = APIRouter()


# ── Methodologies ─────────────────────────────────────────────────────────────

METHODOLOGIES = [
    {
        "module": "SEO",
        "icon": "Globe",
        "fields": [
            {"key": "share_of_voice", "label": "Part de voix SEO", "description": "Pourcentage d'apparitions d'un concurrent dans le top 10 Google par rapport au total des resultats trackes. Formule : (apparitions du concurrent / total des slots top 10) x 100."},
            {"key": "avg_position", "label": "Position moyenne", "description": "Moyenne des positions obtenues par un concurrent dans le top 10 Google, sur l'ensemble des mots-cles ou il apparait. Plus la valeur est basse, meilleur est le positionnement."},
            {"key": "best_keywords", "label": "Meilleurs mots-cles", "description": "Liste des mots-cles ou un concurrent se positionne dans le top 3 (positions 1, 2 ou 3). Indicateur de domination editoriale sur les requetes strategiques."},
            {"key": "missing_keywords", "label": "Mots-cles manquants", "description": "Mots-cles du secteur sur lesquels un concurrent n'apparait dans aucun resultat du top 10. Identifie les opportunites de contenu a creer."},
            {"key": "top_domains", "label": "Top domaines", "description": "Classement des domaines les plus frequemment presents dans le top 10 Google, tous mots-cles confondus. Permet d'identifier les acteurs dominants du secteur."},
        ],
    },
    {
        "module": "GEO",
        "icon": "Sparkles",
        "fields": [
            {"key": "share_of_voice_ia", "label": "Part de voix IA", "description": "Pourcentage de mentions d'un concurrent dans les reponses des moteurs IA (Mistral, Claude, Gemini, ChatGPT). Formule : (mentions du concurrent / total des mentions) x 100."},
            {"key": "avg_position_ia", "label": "Position moyenne IA", "description": "Position moyenne dans l'ordre de citation des reponses IA. Position 1 = premiere marque citee. Calcule sur toutes les reponses ou la marque est mentionnee."},
            {"key": "recommendation_rate", "label": "Taux de recommandation", "description": "Pourcentage de reponses IA ou la marque est explicitement recommandee (pas juste mentionnee). Formule : (reponses avec recommandation / reponses avec mention) x 100."},
            {"key": "sentiment", "label": "Sentiment IA", "description": "Analyse du ton utilise par les moteurs IA lorsqu'ils mentionnent la marque : positif, neutre ou negatif. Base sur l'analyse semantique du contexte de citation."},
            {"key": "seo_vs_geo", "label": "Ecart SEO / GEO", "description": "Difference entre la part de voix SEO (Google) et la part de voix GEO (moteurs IA). Un ecart negatif indique que la marque est moins visible dans les IA que dans Google classique."},
            {"key": "platform_comparison", "label": "Comparaison par plateforme", "description": "Repartition des mentions par moteur IA (Mistral, Claude, Gemini, ChatGPT). Permet d'identifier sur quelle plateforme la marque est la plus ou la moins visible."},
        ],
    },
    {
        "module": "ASO",
        "icon": "Smartphone",
        "fields": [
            {"key": "aso_score", "label": "Score ASO global", "description": "Score composite 0-100 evaluant l'optimisation App Store. Moyenne ponderee : Metadata 25%, Visuel 20%, Note 25%, Avis 15%, Fraicheur 15%."},
            {"key": "metadata_score", "label": "Score Metadata", "description": "Evaluation de la qualite des metadonnees (titre, description, changelog). Poids : 25% du score ASO. Criteres : longueur du titre (ideal 25-30 car), richesse de la description, presence de changelog."},
            {"key": "visual_score", "label": "Score Visuel", "description": "Evaluation des assets visuels : nombre de screenshots (ideal 6+), presence d'une video de preview, qualite de l'icone. Poids : 20% du score ASO."},
            {"key": "rating_score", "label": "Score Note", "description": "Note moyenne de l'app normalisee sur 100. Formule : (note / 5) x 100. Poids : 25% du score ASO."},
            {"key": "freshness_score", "label": "Score Fraicheur", "description": "Mesure de la frequence des mises a jour. 100 = mise a jour < 30 jours, 0 = > 180 jours. Poids : 15% du score ASO."},
        ],
    },
    {
        "module": "Publicites",
        "icon": "Megaphone",
        "fields": [
            {"key": "total_ads", "label": "Total publicites", "description": "Nombre total de publicites detectees dans la Meta Ad Library pour l'ensemble des concurrents trackes."},
            {"key": "format_breakdown", "label": "Repartition par format", "description": "Distribution des publicites par format (image, video, carrousel, etc.). Permet d'identifier les formats privilegies par le secteur."},
            {"key": "estimated_spend", "label": "Budget estime", "description": "Fourchette de budget publicitaire estimee par Meta pour chaque annonceur. Basee sur les donnees de transparence EU de la Ad Library."},
            {"key": "creative_score", "label": "Score creatif", "description": "Score 0-100 evaluant la qualite creative d'une publicite via analyse IA (concept, accroche, ton, composition visuelle, CTA)."},
            {"key": "ad_type", "label": "Type de publicite", "description": "Classification automatique : Branding (notoriete), Performance (conversion/drive), DTS (Drive-to-Store). Basee sur le CTA, l'URL de destination et le concept creatif."},
        ],
    },
    {
        "module": "Geographie",
        "icon": "MapPin",
        "fields": [
            {"key": "store_locations", "label": "Localisations magasins", "description": "Positions GPS des magasins issues de la base BANCO (Base Nationale du Commerce) de data.gouv.fr ou importees manuellement."},
            {"key": "zone_analysis", "label": "Analyse de zone", "description": "Analyse concurrentielle d'une zone geographique definie (rayon ou isochrone). Compte les magasins de chaque enseigne dans le perimetre."},
            {"key": "banco_matching", "label": "Matching BANCO", "description": "Correspondance entre les magasins de l'enseigne et les donnees BANCO. Detecte les ecarts GPS et permet de corriger les positions."},
        ],
    },
]


@router.get("/methodologies")
async def get_methodologies(
    user: User = Depends(get_current_user),
):
    """Return analysis methodology for each module."""
    return METHODOLOGIES


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


# ── Pages Audit (Vertical → Brands → Platforms → Detected pages) ─────────

@router.get("/sectors")
async def get_sectors(user: User = Depends(get_current_user)):
    """List available sectors/verticals."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")
    return list_sectors()


@router.get("/pages-audit")
async def pages_audit(
    sector: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Audit detected pages per competitor per platform. Admin only.

    Groups all active competitors by sector. For each competitor, returns
    the count of detected pages/handles per platform:
    - Facebook: distinct page_ids found in ads + main page + child pages
    - Instagram, TikTok, YouTube, Snapchat: configured handle (0 or 1)
    - Play Store, App Store: configured app ID (0 or 1)
    """
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")

    # Build sector lookup from sectors.py
    name_to_sector: dict[str, str] = {}
    for code, data in SECTORS.items():
        for comp in data.get("competitors", []):
            name_to_sector[comp["name"].lower()] = code

    # Also use Advertiser.sector for competitors linked via join table
    adv_sectors = {}
    for adv_id, sec in db.query(Advertiser.id, Advertiser.sector).filter(Advertiser.sector.isnot(None)).all():
        adv_sectors[adv_id] = sec

    competitors = db.query(Competitor).filter(Competitor.is_active == True).all()
    comp_ids = [c.id for c in competitors]

    # Batch: count distinct page_ids per competitor from ads
    fb_pages_raw = (
        db.query(Ad.competitor_id, Ad.page_id, Ad.page_name, func.count(Ad.id))
        .filter(
            Ad.competitor_id.in_(comp_ids),
            Ad.platform.in_(["facebook", "instagram"]),
            Ad.page_id.isnot(None),
        )
        .group_by(Ad.competitor_id, Ad.page_id, Ad.page_name)
        .all()
    ) if comp_ids else []

    # Organize: competitor_id -> [{page_id, page_name, ads_count}]
    fb_pages_map: dict[int, list] = {}
    for cid, pid, pname, cnt in fb_pages_raw:
        fb_pages_map.setdefault(cid, []).append({
            "page_id": pid,
            "page_name": pname or "Inconnu",
            "ads_count": cnt,
        })

    # Count snapchat ads per competitor
    snap_pages_raw = (
        db.query(Ad.competitor_id, Ad.page_name, func.count(Ad.id))
        .filter(
            Ad.competitor_id.in_(comp_ids),
            Ad.platform == "snapchat",
            Ad.page_name.isnot(None),
        )
        .group_by(Ad.competitor_id, Ad.page_name)
        .all()
    ) if comp_ids else []

    snap_pages_map: dict[int, list] = {}
    for cid, pname, cnt in snap_pages_raw:
        snap_pages_map.setdefault(cid, []).append({
            "page_name": pname or "Inconnu",
            "ads_count": cnt,
        })

    # Count google ads per competitor
    google_pages_raw = (
        db.query(Ad.competitor_id, func.count(Ad.id))
        .filter(
            Ad.competitor_id.in_(comp_ids),
            Ad.platform == "google",
        )
        .group_by(Ad.competitor_id)
        .all()
    ) if comp_ids else []
    google_counts = dict(google_pages_raw)

    # Resolve sector for each competitor
    adv_link_map: dict[int, int] = {}
    if comp_ids:
        for cid, aid in db.query(AdvertiserCompetitor.competitor_id, AdvertiserCompetitor.advertiser_id).filter(
            AdvertiserCompetitor.competitor_id.in_(comp_ids)
        ).all():
            adv_link_map[cid] = aid

    # Build result grouped by sector
    sector_groups: dict[str, list] = {}
    for comp in competitors:
        # Determine sector
        comp_sector = name_to_sector.get(comp.name.lower())
        if not comp_sector:
            adv_id = adv_link_map.get(comp.id)
            comp_sector = adv_sectors.get(adv_id) if adv_id else None
        if not comp_sector:
            comp_sector = "autre"

        if sector and comp_sector != sector:
            continue

        fb_pages = fb_pages_map.get(comp.id, [])
        child_ids = []
        if comp.child_page_ids:
            try:
                child_ids = json.loads(comp.child_page_ids)
            except (json.JSONDecodeError, TypeError):
                pass

        platforms = {
            "facebook": {
                "main_page_id": comp.facebook_page_id,
                "child_page_ids": child_ids,
                "detected_pages": sorted(fb_pages, key=lambda p: p["ads_count"], reverse=True),
                "total_pages": len(set(p["page_id"] for p in fb_pages)),
            },
            "instagram": {
                "handle": comp.instagram_username,
                "configured": bool(comp.instagram_username),
            },
            "tiktok": {
                "handle": comp.tiktok_username,
                "configured": bool(comp.tiktok_username),
            },
            "youtube": {
                "handle": comp.youtube_channel_id,
                "configured": bool(comp.youtube_channel_id),
            },
            "snapchat": {
                "handle": comp.snapchat_entity_name,
                "configured": bool(comp.snapchat_entity_name) or bool(comp.snapchat_username),
                "detected_pages": snap_pages_map.get(comp.id, []),
                "username": comp.snapchat_username,
            },
            "playstore": {
                "handle": comp.playstore_app_id,
                "configured": bool(comp.playstore_app_id),
            },
            "appstore": {
                "handle": comp.appstore_app_id,
                "configured": bool(comp.appstore_app_id),
            },
            "google": {
                "ads_count": google_counts.get(comp.id, 0),
                "configured": google_counts.get(comp.id, 0) > 0,
            },
        }

        sector_groups.setdefault(comp_sector, []).append({
            "id": comp.id,
            "name": comp.name,
            "is_brand": comp.is_brand or False,
            "website": comp.website,
            "platforms": platforms,
        })

    # Deduplicate competitors with same lowercase name within each sector
    for code in sector_groups:
        by_name: dict[str, list] = {}
        for c in sector_groups[code]:
            by_name.setdefault(c["name"].lower(), []).append(c)
        merged = []
        for group in by_name.values():
            if len(group) == 1:
                merged.append(group[0])
                continue
            # Pick canonical: the one with most Facebook detected pages
            canonical = max(group, key=lambda g: len(g["platforms"]["facebook"]["detected_pages"]))
            # Merge detected pages from others into canonical
            seen_page_ids = {p["page_id"] for p in canonical["platforms"]["facebook"]["detected_pages"]}
            for other in group:
                if other["id"] == canonical["id"]:
                    continue
                for page in other["platforms"]["facebook"]["detected_pages"]:
                    if page["page_id"] not in seen_page_ids:
                        canonical["platforms"]["facebook"]["detected_pages"].append(page)
                        seen_page_ids.add(page["page_id"])
                # Merge child_page_ids
                for cid in other["platforms"]["facebook"]["child_page_ids"]:
                    if cid not in canonical["platforms"]["facebook"]["child_page_ids"]:
                        canonical["platforms"]["facebook"]["child_page_ids"].append(cid)
                # Merge snapchat detected pages
                snap_names = {s["page_name"] for s in canonical["platforms"]["snapchat"].get("detected_pages", [])}
                for sp in other["platforms"]["snapchat"].get("detected_pages", []):
                    if sp["page_name"] not in snap_names:
                        canonical["platforms"]["snapchat"]["detected_pages"].append(sp)
                        snap_names.add(sp["page_name"])
                # Take configured handles if canonical lacks them
                for plat in ("instagram", "tiktok", "youtube", "snapchat", "playstore", "appstore"):
                    if not canonical["platforms"][plat].get("configured") and other["platforms"][plat].get("configured"):
                        canonical["platforms"][plat] = other["platforms"][plat]
            # Recount facebook total
            canonical["platforms"]["facebook"]["total_pages"] = len(
                set(p["page_id"] for p in canonical["platforms"]["facebook"]["detected_pages"])
            )
            merged.append(canonical)
        sector_groups[code] = merged

    # Build final response
    result = []
    for code, comps in sorted(sector_groups.items()):
        sector_data = SECTORS.get(code, {})
        result.append({
            "code": code,
            "name": sector_data.get("name", code.capitalize()),
            "competitors": sorted(comps, key=lambda c: c["name"]),
        })

    return result


class PageDeleteRequest(BaseModel):
    competitor_id: int
    platform: str  # facebook, instagram, tiktok, youtube, snapchat, playstore, appstore
    page_id: str | None = None  # For facebook: specific page_id to remove


@router.post("/pages-audit/delete")
async def delete_detected_page(
    body: PageDeleteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a detected page/handle from a competitor. Admin only.

    For Facebook: if page_id is provided, deletes all ads with that page_id
    and removes it from child_page_ids. If no page_id, clears facebook_page_id.
    For other platforms: clears the configured handle.
    """
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")

    comp = db.query(Competitor).filter(Competitor.id == body.competitor_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Concurrent introuvable")

    result = {"competitor": comp.name, "platform": body.platform, "action": ""}

    if body.platform == "facebook":
        if body.page_id:
            # Delete ads with this page_id for this competitor
            deleted = db.query(Ad).filter(
                Ad.competitor_id == comp.id,
                Ad.page_id == body.page_id,
            ).delete(synchronize_session=False)

            # Remove from child_page_ids if present
            if comp.child_page_ids:
                try:
                    children = json.loads(comp.child_page_ids)
                    if body.page_id in children:
                        children.remove(body.page_id)
                        comp.child_page_ids = json.dumps(children) if children else None
                except (json.JSONDecodeError, TypeError):
                    pass

            # If it's the main page_id, clear it
            if comp.facebook_page_id == body.page_id:
                comp.facebook_page_id = None

            result["action"] = f"{deleted} ads supprimées, page {body.page_id} retirée"
        else:
            comp.facebook_page_id = None
            result["action"] = "facebook_page_id vidé"
    elif body.platform == "snapchat":
        if body.page_id:
            # Delete snapchat ads with this page_name
            deleted = db.query(Ad).filter(
                Ad.competitor_id == comp.id,
                Ad.platform == "snapchat",
                Ad.page_name == body.page_id,
            ).delete(synchronize_session=False)
            result["action"] = f"{deleted} ads Snapchat supprimées pour '{body.page_id}'"
        else:
            comp.snapchat_entity_name = None
            result["action"] = "snapchat_entity_name vidé"
    elif body.platform == "google":
        deleted = db.query(Ad).filter(
            Ad.competitor_id == comp.id,
            Ad.platform == "google",
        ).delete(synchronize_session=False)
        result["action"] = f"{deleted} ads Google supprimées"
    else:
        field_map = {
            "instagram": "instagram_username",
            "tiktok": "tiktok_username",
            "youtube": "youtube_channel_id",
            "playstore": "playstore_app_id",
            "appstore": "appstore_app_id",
        }
        field = field_map.get(body.platform)
        if not field:
            raise HTTPException(status_code=400, detail=f"Plateforme inconnue: {body.platform}")
        setattr(comp, field, None)
        result["action"] = f"{field} vidé"

    db.commit()
    return result


# ── Deduplication ─────────────────────────────────────────────────────────────

@router.post("/deduplicate")
async def deduplicate(
    user: User = Depends(get_current_user),
):
    """Merge duplicate competitors by facebook_page_id and name. Admin only."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")
    merged = deduplicate_competitors(engine)
    return {"merged": merged, "message": f"{merged} doublon(s) fusionné(s)"}


# ── User Management ──────────────────────────────────────────────────────────

def _serialize_user(u: User, db: Session) -> dict:
    """Serialize a User to dict with brand/competitor info."""
    from database import UserAdvertiser
    # Get brands via join table
    adv_links = db.query(Advertiser).join(
        UserAdvertiser, UserAdvertiser.advertiser_id == Advertiser.id
    ).filter(UserAdvertiser.user_id == u.id, Advertiser.is_active == True).all()

    brand = adv_links[0] if adv_links else None
    # Count competitors via join tables
    comp_count = 0
    if adv_links:
        adv_ids = [a.id for a in adv_links]
        comp_count = db.query(func.count(AdvertiserCompetitor.competitor_id)).filter(
            AdvertiserCompetitor.advertiser_id.in_(adv_ids)
        ).scalar() or 0

    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "is_active": u.is_active,
        "is_admin": u.is_admin,
        "has_brand": brand is not None,
        "brand_name": brand.company_name if brand else None,
        "competitors_count": comp_count,
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
    return [_serialize_user(u, db) for u in users]


class UserUpdateRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    is_active: bool | None = None
    is_admin: bool | None = None
    password: str | None = None


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a user's profile/status. Admin only."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    updated = []

    if body.name is not None:
        target.name = body.name
        updated.append("name")

    if body.email is not None:
        # Check uniqueness
        existing = db.query(User).filter(User.email == body.email, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"L'email '{body.email}' est déjà utilisé")
        target.email = body.email
        updated.append("email")

    if body.is_active is not None:
        # Prevent admin from deactivating themselves
        if target.id == user.id and not body.is_active:
            raise HTTPException(status_code=400, detail="Impossible de désactiver votre propre compte")
        target.is_active = body.is_active
        updated.append("is_active")

    if body.is_admin is not None:
        # Prevent admin from removing their own admin role
        if target.id == user.id and not body.is_admin:
            raise HTTPException(status_code=400, detail="Impossible de retirer votre propre rôle admin")
        target.is_admin = body.is_admin
        updated.append("is_admin")

    if body.password is not None:
        from core.auth import hash_password
        if len(body.password) < 6:
            raise HTTPException(status_code=400, detail="Le mot de passe doit faire au moins 6 caractères")
        target.password_hash = hash_password(body.password)
        updated.append("password")

    db.commit()
    db.refresh(target)

    return {
        "message": f"Utilisateur '{target.email}' mis à jour",
        "updated_fields": updated,
        "user": _serialize_user(target, db),
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a user. Admin only. Cannot delete yourself."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")

    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Impossible de supprimer votre propre compte")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    email = target.email
    db.delete(target)
    db.commit()

    return {"message": f"Utilisateur '{email}' supprimé"}


# ── Competitor editing (admin) ────────────────────────────────────────────────

class CompetitorEditRequest(BaseModel):
    name: str | None = None
    website: str | None = None
    facebook_page_id: str | None = None
    instagram_username: str | None = None
    tiktok_username: str | None = None
    youtube_channel_id: str | None = None
    playstore_app_id: str | None = None
    appstore_app_id: str | None = None
    snapchat_entity_name: str | None = None


@router.put("/competitors/{competitor_id}")
async def admin_update_competitor(
    competitor_id: int,
    body: CompetitorEditRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update any competitor's handles/info. Admin only, no ownership check."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")

    comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Concurrent introuvable")

    updated = []
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(comp, field, value)
        updated.append(field)

    db.commit()
    db.refresh(comp)

    return {
        "message": f"Concurrent '{comp.name}' mis à jour",
        "updated_fields": updated,
        "competitor": {
            "id": comp.id,
            "name": comp.name,
            "website": comp.website,
            "facebook_page_id": comp.facebook_page_id,
            "instagram_username": comp.instagram_username,
            "tiktok_username": comp.tiktok_username,
            "youtube_channel_id": comp.youtube_channel_id,
            "playstore_app_id": comp.playstore_app_id,
            "appstore_app_id": comp.appstore_app_id,
            "snapchat_entity_name": comp.snapchat_entity_name,
        },
    }


# ── Re-enrichment ────────────────────────────────────────────────────────────

@router.post("/re-enrich/{competitor_id}")
async def admin_re_enrich(
    competitor_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Force re-enrichment of a single competitor. Admin only."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")

    comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Concurrent introuvable")

    from routers.competitors import _auto_enrich_competitor
    results = await _auto_enrich_competitor(comp.id, comp)
    return {
        "message": f"Re-enrichissement terminé pour '{comp.name}'",
        "competitor_id": comp.id,
        "results": results,
    }


@router.post("/re-enrich-all")
async def admin_re_enrich_all(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-enrich ALL active competitors. Admin only."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")

    competitors = db.query(Competitor).filter(Competitor.is_active == True).all()
    from routers.competitors import _auto_enrich_competitor

    summary = []
    for comp in competitors:
        try:
            results = await _auto_enrich_competitor(comp.id, comp)
            summary.append({"id": comp.id, "name": comp.name, "status": "ok", "results": results})
        except Exception as e:
            summary.append({"id": comp.id, "name": comp.name, "status": "error", "error": str(e)})

    ok = sum(1 for s in summary if s["status"] == "ok")
    return {
        "message": f"Re-enrichissement terminé: {ok}/{len(competitors)} OK",
        "total": len(competitors),
        "ok": ok,
        "errors": len(competitors) - ok,
        "details": summary,
    }


# ── Data health ──────────────────────────────────────────────────────────────

@router.get("/data-health")
async def admin_data_health(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Data health report: stale data, missing data, coverage. Admin only."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")

    from datetime import timedelta
    now = datetime.utcnow()
    stale_threshold = now - timedelta(days=7)

    competitors = db.query(Competitor).filter(Competitor.is_active == True).all()
    comp_ids = [c.id for c in competitors]

    # Latest timestamps per competitor per source
    def _latest_map(model, extra_filter=None):
        q = db.query(model.competitor_id, func.max(model.recorded_at).label("latest"))
        if extra_filter is not None:
            q = q.filter(extra_filter)
        return dict(q.filter(model.competitor_id.in_(comp_ids)).group_by(model.competitor_id).all())

    ig_map = _latest_map(InstagramData)
    tt_map = _latest_map(TikTokData)
    yt_map = _latest_map(YouTubeData)
    ps_map = _latest_map(AppData, AppData.store == "playstore")
    as_map = _latest_map(AppData, AppData.store == "appstore")

    # Ad latest per competitor
    ad_map = dict(
        db.query(Ad.competitor_id, func.max(Ad.created_at).label("latest"))
        .filter(Ad.competitor_id.in_(comp_ids))
        .group_by(Ad.competitor_id)
        .all()
    )

    report = []
    never_enriched = []
    stale = []
    # Snapchat ads coverage
    snap_ad_map = dict(
        db.query(Ad.competitor_id, func.max(Ad.created_at).label("latest"))
        .filter(Ad.competitor_id.in_(comp_ids), Ad.platform == "snapchat")
        .group_by(Ad.competitor_id)
        .all()
    )

    coverage = {"instagram": 0, "tiktok": 0, "youtube": 0, "snapchat": 0, "playstore": 0, "appstore": 0, "ads": 0}

    for comp in competitors:
        sources = {
            "instagram": ig_map.get(comp.id),
            "tiktok": tt_map.get(comp.id),
            "youtube": yt_map.get(comp.id),
            "snapchat": snap_ad_map.get(comp.id),
            "playstore": ps_map.get(comp.id),
            "appstore": as_map.get(comp.id),
            "ads": ad_map.get(comp.id),
        }
        all_ts = [v for v in sources.values() if v]
        latest = max(all_ts) if all_ts else None

        # Coverage
        for key, ts in sources.items():
            if ts:
                coverage[key] += 1

        # Never enriched
        if not all_ts:
            never_enriched.append({"id": comp.id, "name": comp.name})
            report.append({"id": comp.id, "name": comp.name, "latest": None, "sources": {k: None for k in sources}, "status": "never"})
            continue

        # Stale
        is_stale = latest and latest < stale_threshold
        if is_stale:
            stale.append({"id": comp.id, "name": comp.name, "latest": latest.isoformat()})

        # Missing handles with no data
        missing = []
        if comp.instagram_username and not ig_map.get(comp.id):
            missing.append("instagram")
        if comp.tiktok_username and not tt_map.get(comp.id):
            missing.append("tiktok")
        if comp.youtube_channel_id and not yt_map.get(comp.id):
            missing.append("youtube")
        if comp.playstore_app_id and not ps_map.get(comp.id):
            missing.append("playstore")
        if comp.appstore_app_id and not as_map.get(comp.id):
            missing.append("appstore")

        report.append({
            "id": comp.id,
            "name": comp.name,
            "latest": latest.isoformat() if latest else None,
            "sources": {k: (v.isoformat() if v else None) for k, v in sources.items()},
            "status": "stale" if is_stale else "ok",
            "missing_data": missing,
        })

    total = len(competitors) or 1
    return {
        "total_competitors": len(competitors),
        "never_enriched": never_enriched,
        "stale": stale,
        "coverage": {k: {"count": v, "pct": round(v / total * 100)} for k, v in coverage.items()},
        "report": report,
    }

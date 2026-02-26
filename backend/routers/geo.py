"""
Geo API router.
Gestion des magasins et analyses de zones de chalandise.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime
import csv
import io
import json

import asyncio
import logging
import random

logger = logging.getLogger(__name__)
from database import get_db, Advertiser, Store, CommuneData, ZoneAnalysis, StoreLocation, Competitor, User, UserAdvertiser, AdvertiserCompetitor
from core.auth import get_current_user, get_optional_user
from core.permissions import parse_advertiser_header
from services.gmb_service import gmb_service
from services.geodata import (
    geodata_service,
    haversine_distance,
    get_bounding_box,
    COMMUNES_REFERENCE,
    find_nearest_commune,
)
from core.retailers_db import get_all_retailers_flat, search_retailers

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class StoreCreate(BaseModel):
    store_code: Optional[str] = None
    name: str
    address: Optional[str] = None
    postal_code: str
    city: str
    department: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    store_type: Optional[str] = None
    surface_m2: Optional[int] = None


class StoreResponse(BaseModel):
    id: int
    store_code: Optional[str]
    name: str
    address: Optional[str]
    postal_code: str
    city: str
    department: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    store_type: Optional[str]
    surface_m2: Optional[int]
    is_active: bool

    class Config:
        from_attributes = True


class ZoneAnalysisRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = Field(default=10, ge=1, le=50)


class ZoneAnalysisResponse(BaseModel):
    center: Dict[str, float]
    radius_km: float
    nb_communes: int
    population_totale: int
    loyer_moyen_m2: Optional[float]
    revenu_median_moyen: Optional[float]
    communes: List[Dict[str, Any]]
    concurrents_proches: List[Dict[str, Any]] = []


class MapDataResponse(BaseModel):
    stores: List[Dict[str, Any]]
    communes: List[Dict[str, Any]]
    stats: Dict[str, Any]


# =============================================================================
# Endpoints - Magasins
# =============================================================================

@router.get("/stores", response_model=List[StoreResponse])
async def list_stores(
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Liste les magasins de l'enseigne."""
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    query = db.query(Advertiser).filter(Advertiser.is_active == True)
    if user:
        query = query.filter(Advertiser.id.in_(user_adv_ids))
    if x_advertiser_id:
        query = query.filter(Advertiser.id == int(x_advertiser_id))
    brand = query.first()
    if not brand:
        return []

    query = db.query(Store).filter(
        Store.advertiser_id == brand.id,
        Store.is_active == True
    )

    if department:
        query = query.filter(Store.department == department)

    return [StoreResponse.model_validate(s) for s in query.all()]


@router.post("/stores")
async def create_store(
    data: StoreCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Ajoute un magasin."""
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    brand_query = db.query(Advertiser).filter(Advertiser.is_active == True)
    if user:
        brand_query = brand_query.filter(Advertiser.id.in_(user_adv_ids))
    if x_advertiser_id:
        brand_query = brand_query.filter(Advertiser.id == int(x_advertiser_id))
    brand = brand_query.first()
    if not brand:
        raise HTTPException(status_code=404, detail="Aucune enseigne configurée")

    # Déduit le département du code postal si non fourni
    department = data.department
    if not department and data.postal_code:
        department = data.postal_code[:2]
        if department == "20":  # Corse
            department = "2A" if int(data.postal_code) < 20200 else "2B"

    store = Store(
        advertiser_id=brand.id,
        store_code=data.store_code,
        name=data.name,
        address=data.address,
        postal_code=data.postal_code,
        city=data.city,
        department=department,
        region=data.region,
        latitude=data.latitude,
        longitude=data.longitude,
        store_type=data.store_type,
        surface_m2=data.surface_m2,
    )
    db.add(store)
    db.commit()
    db.refresh(store)

    return store


@router.post("/stores/upload")
async def upload_stores(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Upload massif de magasins via CSV.

    Format attendu (colonnes):
    - name (obligatoire)
    - postal_code (obligatoire)
    - city (obligatoire)
    - address
    - latitude
    - longitude
    - store_code
    - store_type
    - surface_m2
    """
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    brand_query = db.query(Advertiser).filter(Advertiser.is_active == True)
    if user:
        brand_query = brand_query.filter(Advertiser.id.in_(user_adv_ids))
    if x_advertiser_id:
        brand_query = brand_query.filter(Advertiser.id == int(x_advertiser_id))
    brand = brand_query.first()
    if not brand:
        raise HTTPException(status_code=404, detail="Aucune enseigne configurée")

    # Lit le fichier CSV
    content = await file.read()

    # Essaie plusieurs encodages
    for encoding in ["utf-8", "latin-1", "cp1252"]:
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(status_code=400, detail="Encodage du fichier non supporté")

    # Parse le CSV
    reader = csv.DictReader(io.StringIO(text), delimiter=";")

    added = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        try:
            name = row.get("name") or row.get("nom") or row.get("NAME")
            postal_code = row.get("postal_code") or row.get("code_postal") or row.get("CP")
            city = row.get("city") or row.get("ville") or row.get("VILLE")

            if not name or not postal_code or not city:
                errors.append(f"Ligne {i}: champs obligatoires manquants")
                continue

            # Parse les coordonnées
            lat = None
            lon = None
            lat_str = row.get("latitude") or row.get("lat") or row.get("LATITUDE")
            lon_str = row.get("longitude") or row.get("lon") or row.get("LONGITUDE")

            if lat_str and lon_str:
                try:
                    lat = float(lat_str.replace(",", "."))
                    lon = float(lon_str.replace(",", "."))
                except ValueError:
                    pass

            # Déduit le département
            department = postal_code[:2]
            if department == "20":
                department = "2A" if int(postal_code) < 20200 else "2B"

            store = Store(
                advertiser_id=brand.id,
                store_code=row.get("store_code") or row.get("code"),
                name=name,
                address=row.get("address") or row.get("adresse"),
                postal_code=postal_code,
                city=city,
                department=department,
                latitude=lat,
                longitude=lon,
                store_type=row.get("store_type") or row.get("type"),
                surface_m2=int(row.get("surface_m2") or row.get("surface") or 0) or None,
            )
            db.add(store)
            added += 1

        except Exception as e:
            errors.append(f"Ligne {i}: {str(e)}")

    db.commit()

    return {
        "message": f"{added} magasins importés",
        "added": added,
        "errors": errors[:10],  # Max 10 erreurs retournées
        "total_errors": len(errors),
    }


@router.delete("/stores/{store_id}")
async def delete_store(store_id: int, db: Session = Depends(get_db)):
    """Supprime un magasin."""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Magasin non trouvé")

    store.is_active = False
    db.commit()

    return {"message": f"Magasin '{store.name}' supprimé"}


# =============================================================================
# Endpoints - Analyse de zone
# =============================================================================

@router.post("/zone/analyze")
async def analyze_zone(
    data: ZoneAnalysisRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Analyse une zone de chalandise.

    Retourne les données démographiques et économiques
    dans un rayon autour d'un point.
    """
    # Utilise les communes de référence avec estimation
    communes_with_data = []

    for commune in COMMUNES_REFERENCE:
        distance = haversine_distance(
            data.latitude, data.longitude,
            commune["lat"], commune["lon"]
        )

        if distance <= data.radius_km:
            communes_with_data.append({
                "code_commune": commune["code"],
                "nom_commune": commune["nom"],
                "population": commune["pop"],
                "latitude": commune["lat"],
                "longitude": commune["lon"],
                "distance_km": round(distance, 2),
            })

    # Agrégations
    total_pop = sum(c["population"] for c in communes_with_data)

    # Cherche les concurrents proches (autres magasins en base)
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    brand_query = db.query(Advertiser).filter(Advertiser.is_active == True)
    if user:
        brand_query = brand_query.filter(Advertiser.id.in_(user_adv_ids))
    if x_advertiser_id:
        brand_query = brand_query.filter(Advertiser.id == int(x_advertiser_id))
    brand = brand_query.first()
    concurrents = []

    if brand:
        all_stores = db.query(Store).filter(
            Store.advertiser_id != brand.id,
            Store.latitude.isnot(None),
            Store.longitude.isnot(None)
        ).all()

        for store in all_stores:
            distance = haversine_distance(
                data.latitude, data.longitude,
                store.latitude, store.longitude
            )
            if distance <= data.radius_km:
                concurrents.append({
                    "name": store.name,
                    "city": store.city,
                    "distance_km": round(distance, 2),
                })

    return ZoneAnalysisResponse(
        center={"latitude": data.latitude, "longitude": data.longitude},
        radius_km=data.radius_km,
        nb_communes=len(communes_with_data),
        population_totale=total_pop,
        loyer_moyen_m2=None,  # Sera enrichi par les données data.gouv.fr
        revenu_median_moyen=None,
        communes=sorted(communes_with_data, key=lambda x: x["distance_km"]),
        concurrents_proches=sorted(concurrents, key=lambda x: x["distance_km"]),
    )


@router.get("/zone/store/{store_id}")
async def analyze_store_zone(
    store_id: int,
    radius_km: float = 10,
    db: Session = Depends(get_db)
):
    """Analyse la zone de chalandise d'un magasin."""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Magasin non trouvé")

    if not store.latitude or not store.longitude:
        raise HTTPException(
            status_code=400,
            detail="Coordonnées GPS manquantes pour ce magasin"
        )

    # Réutilise l'analyse de zone
    return await analyze_zone(
        ZoneAnalysisRequest(
            latitude=store.latitude,
            longitude=store.longitude,
            radius_km=radius_km
        ),
        db
    )


# =============================================================================
# Endpoints - Carte et données
# =============================================================================

@router.get("/map/data")
async def get_map_data(
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Données pour affichage carte de France.

    Retourne les magasins et les données par commune
    pour superposition cartographique.
    """
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    brand_query = db.query(Advertiser).filter(Advertiser.is_active == True)
    if user:
        brand_query = brand_query.filter(Advertiser.id.in_(user_adv_ids))
    if x_advertiser_id:
        brand_query = brand_query.filter(Advertiser.id == int(x_advertiser_id))
    brand = brand_query.first()

    # Magasins
    stores_query = db.query(Store).filter(Store.is_active == True)
    if brand:
        stores_query = stores_query.filter(Store.advertiser_id == brand.id)
    if department:
        stores_query = stores_query.filter(Store.department == department)

    stores = [
        {
            "id": s.id,
            "name": s.name,
            "city": s.city,
            "postal_code": s.postal_code,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "store_type": s.store_type,
        }
        for s in stores_query.all()
    ]

    # Communes de référence
    communes = COMMUNES_REFERENCE
    if department:
        communes = [c for c in communes if c["dep"] == department]

    # Stats
    total_stores = len(stores)
    stores_with_gps = len([s for s in stores if s["latitude"]])
    departments_covered = len(set(s["postal_code"][:2] for s in stores if s.get("postal_code")))

    return {
        "stores": stores,
        "communes": communes,
        "stats": {
            "total_stores": total_stores,
            "stores_with_gps": stores_with_gps,
            "departments_covered": departments_covered,
            "brand_name": brand.company_name if brand else None,
        }
    }


@router.get("/map/heatmap")
async def get_heatmap_data(
    metric: str = "population",
    db: Session = Depends(get_db)
):
    """
    Données pour heatmap France.

    Métriques disponibles: population, loyers, equipements
    """
    data = []

    for commune in COMMUNES_REFERENCE:
        value = commune.get("pop", 0)

        if metric == "loyers":
            # Estimation loyers basée sur la taille de la ville
            value = 15 + (commune.get("pop", 0) / 100000) * 5

        elif metric == "equipements":
            # Estimation équipements
            value = commune.get("pop", 0) / 1000

        data.append({
            "code": commune["code"],
            "nom": commune["nom"],
            "lat": commune["lat"],
            "lon": commune["lon"],
            "value": round(value, 2),
        })

    return {
        "metric": metric,
        "data": data,
        "legend": {
            "population": {"unit": "habitants", "label": "Population"},
            "loyers": {"unit": "€/m²", "label": "Loyer moyen"},
            "equipements": {"unit": "nb", "label": "Équipements"},
        }.get(metric, {}),
    }


# =============================================================================
# Endpoints - Magasins concurrents
# =============================================================================

COMPETITOR_COLORS = {
    # Grande distribution
    "carrefour": "#3b82f6",
    "leclerc": "#22c55e",
    "lidl": "#fbbf24",
    "auchan": "#ef4444",
    "intermarché": "#f97316",
    "casino": "#8b5cf6",
    "monoprix": "#ec4899",
    "système u": "#14b8a6",
    "cora": "#6366f1",
    # Bricolage / Maison
    "castorama": "#f97316",
    "leroy merlin": "#22c55e",
    "brico dépôt": "#eab308",
    "bricomarché": "#3b82f6",
    "mr bricolage": "#ef4444",
    "ikea": "#0ea5e9",
    "conforama": "#ec4899",
    "but": "#8b5cf6",
    # Sport
    "decathlon": "#3b82f6",
    "intersport": "#ef4444",
    # Mode
    "kiabi": "#ec4899",
    "zara": "#000000",
}


@router.get("/competitor-stores")
async def get_all_competitor_stores(
    include_stores: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Retourne les magasins concurrents groupés par concurrent.

    Par défaut ne renvoie que les comptages (léger).
    Passer include_stores=true pour obtenir le détail de chaque magasin (carte).
    Filtre par les concurrents de l'utilisateur connecté.
    """
    from sqlalchemy import func

    # Get the user's competitor IDs to filter store locations
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    comp_ids_from_adv = [r[0] for r in db.query(AdvertiserCompetitor.competitor_id).filter(AdvertiserCompetitor.advertiser_id.in_(user_adv_ids)).all()]
    user_comp_query = db.query(Competitor.id).filter((Competitor.is_active == True) | (Competitor.is_active == None))
    # Exclude the brand itself from its own competitor list
    user_comp_query = user_comp_query.filter((Competitor.is_brand == False) | (Competitor.is_brand == None))
    if user:
        user_comp_query = user_comp_query.filter(Competitor.id.in_(comp_ids_from_adv))
    if x_advertiser_id:
        user_comp_query = user_comp_query.filter(Competitor.advertiser_id == int(x_advertiser_id))
    user_comp_ids = [row[0] for row in user_comp_query.all()]

    if not user_comp_ids:
        return {"total_competitors": 0, "total_stores": 0, "competitors": []}

    # Always get counts via aggregate query (lightweight)
    counts = (
        db.query(
            StoreLocation.competitor_id,
            func.count(StoreLocation.id).label("total"),
        )
        .filter(
            StoreLocation.source == "BANCO",
            StoreLocation.competitor_id.in_(user_comp_ids),
            StoreLocation.latitude.isnot(None),
            StoreLocation.longitude.isnot(None),
        )
        .group_by(StoreLocation.competitor_id)
        .all()
    )

    # Build competitor info
    comp_ids = [c[0] for c in counts]
    competitors_map = {}
    if comp_ids:
        comps = db.query(Competitor).filter(Competitor.id.in_(comp_ids)).all()
        competitors_map = {c.id: c for c in comps}

    result = []
    total_stores = 0
    for comp_id, count in counts:
        comp = competitors_map.get(comp_id)
        comp_name = comp.name if comp else "Inconnu"
        color = COMPETITOR_COLORS.get(comp_name.lower(), "#6b7280")
        total_stores += count

        entry = {
            "competitor_id": comp_id,
            "competitor_name": comp_name,
            "color": color,
            "logo_url": comp.logo_url if comp else None,
            "total": count,
        }

        if include_stores:
            stores = db.query(StoreLocation).filter(
                StoreLocation.source == "BANCO",
                StoreLocation.competitor_id == comp_id,
                StoreLocation.latitude.isnot(None),
                StoreLocation.longitude.isnot(None),
            ).all()
            entry["stores"] = [
                {
                    "id": s.id,
                    "name": s.name,
                    "brand_name": s.brand_name,
                    "category": s.category,
                    "city": s.city,
                    "postal_code": s.postal_code,
                    "latitude": s.latitude,
                    "longitude": s.longitude,
                    "google_rating": s.google_rating,
                    "google_reviews_count": s.google_reviews_count,
                }
                for s in stores
            ]

            # GMB aggregates
            rated = [s for s in stores if s.google_rating is not None]
            if rated:
                entry["avg_rating"] = round(sum(s.google_rating for s in rated) / len(rated), 2)
                entry["total_reviews"] = sum(s.google_reviews_count or 0 for s in rated)
                entry["stores_with_rating"] = len(rated)

        result.append(entry)

    return {
        "total_competitors": len(result),
        "total_stores": total_stores,
        "competitors": result,
    }


@router.get("/competitor-stores/{competitor_id}")
async def get_competitor_stores_geo(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Magasins d'un concurrent spécifique."""
    # Verify competitor belongs to this user via join tables
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    comp_ids_from_adv = [r[0] for r in db.query(AdvertiserCompetitor.competitor_id).filter(AdvertiserCompetitor.advertiser_id.in_(user_adv_ids)).all()]
    comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if user and comp and comp.id not in comp_ids_from_adv:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")
    if x_advertiser_id and comp and comp.advertiser_id != int(x_advertiser_id):
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")

    stores = db.query(StoreLocation).filter(
        StoreLocation.competitor_id == competitor_id,
        StoreLocation.source == "BANCO",
        StoreLocation.latitude.isnot(None),
    ).all()

    return {
        "competitor_id": competitor_id,
        "competitor_name": comp.name if comp else "Inconnu",
        "total": len(stores),
        "stores": [
            {
                "id": s.id,
                "name": s.name,
                "city": s.city,
                "latitude": s.latitude,
                "longitude": s.longitude,
            }
            for s in stores
        ],
    }


# =============================================================================
# Endpoints - Zones de chalandise concurrents
# =============================================================================

@router.get("/catchment-zones")
async def get_catchment_zones(
    radius_km: float = 10,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Calcule les zones de chalandise de chaque concurrent.

    Pour chaque magasin concurrent, détermine les communes couvertes dans un rayon donné,
    agrège la population couverte, et calcule les chevauchements entre concurrents.
    """
    import time
    start = time.time()

    if radius_km < 1 or radius_km > 50:
        raise HTTPException(status_code=400, detail="radius_km doit être entre 1 et 50")

    # 1. Load communes with coordinates + population
    all_communes = await datagouv_service.get_communes_with_data()
    communes_with_coords = [
        c for c in all_communes
        if c.get("latitude") and c.get("longitude") and c.get("population")
    ]

    # 2. Load competitor stores (BANCO source)
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    comp_ids_from_adv = [r[0] for r in db.query(AdvertiserCompetitor.competitor_id).filter(AdvertiserCompetitor.advertiser_id.in_(user_adv_ids)).all()]
    user_comp_query = db.query(Competitor.id, Competitor.name).filter((Competitor.is_active == True) | (Competitor.is_active == None))
    if user:
        user_comp_query = user_comp_query.filter(Competitor.id.in_(comp_ids_from_adv))
    if x_advertiser_id:
        user_comp_query = user_comp_query.filter(Competitor.advertiser_id == int(x_advertiser_id))
    competitors_list = user_comp_query.all()

    if not competitors_list:
        return {"radius_km": radius_km, "total_population_france": 67000000,
                "competitors": [], "overlaps": [], "computation_time_ms": 0}

    comp_map = {c.id: c.name for c in competitors_list}
    comp_ids = list(comp_map.keys())

    stores = db.query(StoreLocation).filter(
        StoreLocation.source == "BANCO",
        StoreLocation.competitor_id.in_(comp_ids),
        StoreLocation.latitude.isnot(None),
        StoreLocation.longitude.isnot(None),
    ).all()

    # Group stores by competitor
    stores_by_comp: Dict[int, list] = {}
    for s in stores:
        stores_by_comp.setdefault(s.competitor_id, []).append(s)

    # 3. For each store, find communes in radius using bbox pre-filter + haversine
    # Result: dict[competitor_id] -> dict[commune_code] -> {population, min_distance}
    comp_communes: Dict[int, Dict[str, Dict]] = {}

    for comp_id, comp_stores in stores_by_comp.items():
        covered: Dict[str, Dict] = {}
        for store in comp_stores:
            bbox = get_bounding_box(store.latitude, store.longitude, radius_km)
            for commune in communes_with_coords:
                clat = commune["latitude"]
                clon = commune["longitude"]
                # Quick bbox filter
                if clat < bbox["min_lat"] or clat > bbox["max_lat"]:
                    continue
                if clon < bbox["min_lon"] or clon > bbox["max_lon"]:
                    continue
                # Precise haversine
                dist = haversine_distance(store.latitude, store.longitude, clat, clon)
                if dist <= radius_km:
                    code = commune.get("code", "")
                    if not code:
                        continue
                    if code not in covered or dist < covered[code]["distance"]:
                        covered[code] = {
                            "population": commune.get("population", 0),
                            "distance": dist,
                        }
        comp_communes[comp_id] = covered

    # 4. Aggregate per competitor
    total_pop_france = sum(c.get("population", 0) for c in communes_with_coords)
    if total_pop_france == 0:
        total_pop_france = 67000000

    competitors_result = []
    for comp_id in comp_ids:
        covered = comp_communes.get(comp_id, {})
        pop_covered = sum(v["population"] for v in covered.values())
        nb_communes = len(covered)
        name = comp_map[comp_id]
        color = COMPETITOR_COLORS.get(name.lower(), "#6b7280")
        total_stores = len(stores_by_comp.get(comp_id, []))
        pct = round(pop_covered / total_pop_france * 100, 1) if total_pop_france > 0 else 0

        competitors_result.append({
            "competitor_id": comp_id,
            "competitor_name": name,
            "color": color,
            "total_stores": total_stores,
            "population_covered": pop_covered,
            "nb_communes_covered": nb_communes,
            "pct_population": pct,
        })

    # Sort by population covered descending
    competitors_result.sort(key=lambda x: x["population_covered"], reverse=True)

    # 5. Compute pairwise overlaps
    overlaps = []
    comp_id_list = [c["competitor_id"] for c in competitors_result]
    for i in range(len(comp_id_list)):
        for j in range(i + 1, len(comp_id_list)):
            a_id = comp_id_list[i]
            b_id = comp_id_list[j]
            a_codes = set(comp_communes.get(a_id, {}).keys())
            b_codes = set(comp_communes.get(b_id, {}).keys())
            shared = a_codes & b_codes
            if not shared:
                continue
            shared_pop = sum(
                comp_communes[a_id][code]["population"]
                for code in shared
            )
            overlaps.append({
                "competitor_a_name": comp_map[a_id],
                "competitor_b_name": comp_map[b_id],
                "shared_population": shared_pop,
                "shared_communes": len(shared),
            })

    overlaps.sort(key=lambda x: x["shared_population"], reverse=True)

    elapsed_ms = round((time.time() - start) * 1000)

    return {
        "radius_km": radius_km,
        "total_population_france": total_pop_france,
        "competitors": competitors_result,
        "overlaps": overlaps,
        "computation_time_ms": elapsed_ms,
    }


# =============================================================================
# Endpoints - Base commerces management
# =============================================================================

@router.post("/banco/download")
async def download_banco():
    """Télécharge/rafraîchit la base nationale des commerces."""
    from services.banco import banco_service
    count = await banco_service.download(force=True)
    return {"message": f"Base commerces téléchargée: {count} commerces avec enseigne", "count": count}


@router.get("/banco/brands")
async def list_banco_brands():
    """Liste les enseignes disponibles dans la base commerces."""
    from services.banco import banco_service
    brands = await banco_service.get_all_brands()
    return {"total": len(brands), "brands": brands[:100]}


@router.post("/banco/enrich/{competitor_id}")
async def enrich_one_competitor(competitor_id: int, db: Session = Depends(get_db)):
    """Enrichit un seul concurrent avec la base BANCO."""
    import traceback as tb
    try:
        from services.banco import banco_service

        comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
        if not comp:
            raise HTTPException(status_code=404, detail="Concurrent non trouvé")

        count = await banco_service.search_and_store(comp.id, comp.name, db)
        return {"competitor": comp.name, "competitor_id": comp.id, "stores_found": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BANCO enrich error: {tb.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/banco/enrich-all")
async def enrich_all_competitors(db: Session = Depends(get_db)):
    """Enrichit tous les concurrents existants avec la base commerces.
    Retourne immédiatement la liste des concurrents à enrichir, puis les enrichit un par un."""
    import traceback as tb
    try:
        from services.banco import banco_service

        # Get unique competitor names (deduplicate across advertisers)
        rows = db.query(Competitor.id, Competitor.name).all()
        logger.info(f"BANCO enrich-all: {len(rows)} competitor rows to process")

        # Deduplicate by name (same brand across multiple advertisers)
        seen_names: dict[str, list[int]] = {}
        for cid, cname in rows:
            key = (cname or "").strip().lower()
            if key:
                seen_names.setdefault(key, []).append(cid)

        # Return the list immediately for client-side batching
        return {
            "message": f"{len(seen_names)} enseignes uniques à enrichir ({len(rows)} competitor rows)",
            "unique_brands": len(seen_names),
            "total_competitors": len(rows),
            "competitors": [
                {"name": name_key, "ids": comp_ids}
                for name_key, comp_ids in seen_names.items()
            ],
        }
    except Exception as e:
        logger.error(f"BANCO enrich-all FATAL: {tb.format_exc()}")
        return {"error": str(e), "traceback": tb.format_exc()}


# =============================================================================
# Endpoints - Enrichissement GMB demo
# =============================================================================

# Average ratings by enseigne (realistic variation)
ENSEIGNE_RATING_CENTERS = {
    "carrefour": 3.9,
    "leclerc": 4.1,
    "lidl": 4.0,
    "auchan": 3.8,
    "intermarché": 4.0,
    "casino": 3.7,
    "monoprix": 4.2,
    "système u": 4.1,
    "cora": 3.9,
    "castorama": 3.8,
    "leroy merlin": 4.3,
    "brico dépôt": 3.6,
    "bricomarché": 3.9,
    "mr bricolage": 3.7,
    "ikea": 4.1,
    "conforama": 3.5,
    "but": 3.6,
    "decathlon": 4.4,
    "intersport": 4.0,
    "kiabi": 4.1,
    "zara": 3.9,
}

# City population tiers for review count scaling
BIG_CITIES = {"paris", "marseille", "lyon", "toulouse", "nice", "nantes", "strasbourg", "montpellier", "bordeaux", "lille", "rennes", "reims", "toulon", "grenoble", "dijon", "angers", "nîmes", "saint-étienne"}
MEDIUM_CITIES = {"le mans", "aix-en-provence", "clermont-ferrand", "brest", "tours", "amiens", "limoges", "perpignan", "metz", "besançon", "orléans", "rouen", "mulhouse", "caen", "nancy", "argenteuil", "saint-denis", "montreuil", "avignon", "dunkerque", "poitiers", "pau", "calais", "la rochelle", "colmar", "lorient", "troyes", "bayonne"}


@router.post("/stores/enrich-gmb")
async def enrich_gmb(
    force: bool = False,
    max_per_run: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Enrichit les store_locations avec des données Google My Business réelles.
    Utilise SearchAPI Google Maps (primaire) + Google Places API (fallback).
    - force=true : ré-enrichit tous les magasins (même ceux déjà enrichis)
    - max_per_run : limite le nombre de requêtes API par exécution (défaut 50)
    """
    logger = logging.getLogger(__name__)

    if not gmb_service.is_configured:
        raise HTTPException(status_code=503, detail="GMB service not configured (no SearchAPI or Google Places key)")

    # Filter stores by user's competitors
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    comp_ids_from_adv = [r[0] for r in db.query(AdvertiserCompetitor.competitor_id).filter(AdvertiserCompetitor.advertiser_id.in_(user_adv_ids)).all()]
    user_comp_query = db.query(Competitor.id, Competitor.name).filter((Competitor.is_active == True) | (Competitor.is_active == None))
    if user:
        user_comp_query = user_comp_query.filter(Competitor.id.in_(comp_ids_from_adv))
    if x_advertiser_id:
        user_comp_query = user_comp_query.filter(Competitor.advertiser_id == int(x_advertiser_id))
    competitors_list = user_comp_query.all()
    comp_map = {c.id: c.name for c in competitors_list}
    comp_ids = list(comp_map.keys())

    if not comp_ids:
        return {"message": "Aucun concurrent trouvé", "enriched": 0}

    # Get stores to enrich (all if force, only missing otherwise)
    base_filter = [
        StoreLocation.competitor_id.in_(comp_ids),
        StoreLocation.source == "BANCO",
    ]
    if not force:
        base_filter.append(StoreLocation.google_rating.is_(None))

    stores = db.query(StoreLocation).filter(*base_filter).all()

    if not stores:
        already = db.query(StoreLocation).filter(
            StoreLocation.competitor_id.in_(comp_ids),
            StoreLocation.source == "BANCO",
            StoreLocation.google_rating.isnot(None),
        ).count()
        return {"message": f"Tous les magasins sont déjà enrichis ({already})", "enriched": 0, "already_enriched": already}

    # Limit to max_per_run to preserve SearchAPI quota
    stores_to_process = stores[:max_per_run]
    total_pending = len(stores)

    now = datetime.utcnow()
    enriched_count = 0
    errors_count = 0
    by_competitor: dict[str, dict] = {}

    for store in stores_to_process:
        comp_name = comp_map.get(store.competitor_id, "inconnu")

        result = await gmb_service.enrich_store(
            store_name=store.name or "",
            brand_name=comp_name,
            city=store.city or "",
            latitude=store.latitude,
            longitude=store.longitude,
        )

        if result.get("success"):
            store.google_rating = result.get("rating")
            store.google_reviews_count = result.get("reviews_count")
            store.google_place_id = result.get("place_id")
            store.rating_fetched_at = now
            enriched_count += 1

            # Track per-competitor stats
            if comp_name not in by_competitor:
                by_competitor[comp_name] = {"enriched": 0, "errors": 0, "ratings_sum": 0.0}
            by_competitor[comp_name]["enriched"] += 1
            if result.get("rating"):
                by_competitor[comp_name]["ratings_sum"] += result["rating"]
        else:
            errors_count += 1
            if comp_name not in by_competitor:
                by_competitor[comp_name] = {"enriched": 0, "errors": 0, "ratings_sum": 0.0}
            by_competitor[comp_name]["errors"] += 1
            logger.warning(f"GMB enrichment failed for {comp_name} - {store.city}: {result.get('error')}")

        # Rate limit between API calls
        await asyncio.sleep(1.1)

    db.commit()

    summary = [
        {
            "competitor": name,
            "enriched": stats["enriched"],
            "errors": stats["errors"],
            "avg_rating": round(stats["ratings_sum"] / stats["enriched"], 2) if stats["enriched"] > 0 else None,
        }
        for name, stats in by_competitor.items()
    ]

    remaining = total_pending - len(stores_to_process)

    return {
        "message": f"{enriched_count} magasins enrichis via GMB réel ({errors_count} erreurs)",
        "enriched": enriched_count,
        "errors": errors_count,
        "remaining": remaining,
        "api_calls_used": len(stores_to_process),
        "by_competitor": summary,
    }


@router.post("/stores/enrich-gmb-demo")
async def enrich_gmb_demo(
    force: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Fallback : enrichit les store_locations avec des données GMB de démo (ratings simulés).
    Utilisé quand aucune API GMB n'est configurée ou pour tester sans consommer de quota.
    """
    # Filter stores by user's competitors
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    comp_ids_from_adv = [r[0] for r in db.query(AdvertiserCompetitor.competitor_id).filter(AdvertiserCompetitor.advertiser_id.in_(user_adv_ids)).all()]
    user_comp_query = db.query(Competitor.id, Competitor.name).filter((Competitor.is_active == True) | (Competitor.is_active == None))
    if user:
        user_comp_query = user_comp_query.filter(Competitor.id.in_(comp_ids_from_adv))
    if x_advertiser_id:
        user_comp_query = user_comp_query.filter(Competitor.advertiser_id == int(x_advertiser_id))
    competitors_list = user_comp_query.all()
    comp_map = {c.id: c.name for c in competitors_list}
    comp_ids = list(comp_map.keys())

    if not comp_ids:
        return {"message": "Aucun concurrent trouvé", "enriched": 0}

    base_filter = [
        StoreLocation.competitor_id.in_(comp_ids),
        StoreLocation.source == "BANCO",
    ]
    if not force:
        base_filter.append(StoreLocation.google_rating.is_(None))

    stores = db.query(StoreLocation).filter(*base_filter).all()

    if not stores:
        already = db.query(StoreLocation).filter(
            StoreLocation.competitor_id.in_(comp_ids),
            StoreLocation.source == "BANCO",
            StoreLocation.google_rating.isnot(None),
        ).count()
        return {"message": f"Tous les magasins sont déjà enrichis ({already})", "enriched": 0, "already_enriched": already}

    now = datetime.utcnow()
    enriched_count = 0
    by_competitor: dict[str, dict] = {}

    for store in stores:
        comp_name = comp_map.get(store.competitor_id, "inconnu")
        center = ENSEIGNE_RATING_CENTERS.get(comp_name.lower(), 4.0)

        rating = round(min(5.0, max(2.5, random.gauss(center, 0.35))), 1)

        city_lower = (store.city or "").lower().strip()
        if city_lower in BIG_CITIES:
            reviews = random.randint(400, 2500)
        elif city_lower in MEDIUM_CITIES:
            reviews = random.randint(150, 800)
        else:
            reviews = random.randint(50, 400)

        store.google_rating = rating
        store.google_reviews_count = reviews
        store.google_place_id = f"ChIJ_demo_{store.id}"
        store.rating_fetched_at = now
        enriched_count += 1

        key = comp_name
        if key not in by_competitor:
            by_competitor[key] = {"enriched": 0, "ratings_sum": 0.0}
        by_competitor[key]["enriched"] += 1
        by_competitor[key]["ratings_sum"] += rating

    db.commit()

    summary = [
        {
            "competitor": name,
            "enriched": stats["enriched"],
            "avg_rating": round(stats["ratings_sum"] / stats["enriched"], 2),
        }
        for name, stats in by_competitor.items()
    ]

    return {
        "message": f"{enriched_count} magasins enrichis avec données GMB demo",
        "enriched": enriched_count,
        "by_competitor": summary,
    }


# =============================================================================
# Endpoints - Base retailers
# =============================================================================

@router.get("/retailers")
async def list_retailers(sector: Optional[str] = None):
    """Liste tous les retailers de la base."""
    retailers = get_all_retailers_flat()

    if sector:
        retailers = [r for r in retailers if r["sector"] == sector]

    return {
        "total": len(retailers),
        "retailers": retailers,
    }


@router.get("/retailers/search")
async def search_retailers_endpoint(q: str):
    """Recherche un retailer par nom."""
    results = search_retailers(q)
    return {
        "query": q,
        "results": results,
    }


# =============================================================================
# Endpoints - Enrichissement data.gouv.fr
# =============================================================================

from services.datagouv import datagouv_service

@router.get("/data/communes")
async def get_communes_data(
    department: Optional[str] = None,
    limit: int = 100,
):
    """
    Liste des communes avec données population.
    Source: INSEE via data.gouv.fr
    """
    communes = await datagouv_service.get_communes_with_data(
        department=department,
        limit=limit,
    )
    return {
        "total": len(communes),
        "department": department,
        "communes": communes,
    }


@router.get("/data/loyers")
async def get_loyers_data(department: Optional[str] = None):
    """
    Données de loyers par commune.
    Source: Carte des loyers data.gouv.fr
    """
    loyers = await datagouv_service.get_loyers_data(department=department)
    return {
        "total": len(loyers),
        "department": department,
        "data": loyers[:100],  # Limite pour la réponse
        "source": "data.gouv.fr - Carte des loyers",
    }


@router.get("/data/revenus")
async def get_revenus_data(department: Optional[str] = None):
    """
    Revenus médians par commune.
    Source: INSEE via data.gouv.fr
    """
    revenus = await datagouv_service.get_revenus_data(department=department)
    return {
        "total": len(revenus),
        "department": department,
        "data": revenus[:100],
        "source": "data.gouv.fr - Revenus fiscaux INSEE",
    }


@router.get("/data/cache-status")
async def get_cache_status():
    """Statut du cache des datasets data.gouv.fr."""
    return datagouv_service.get_cache_status()


@router.post("/data/refresh")
async def refresh_datasets():
    """Force le rafraîchissement des datasets data.gouv.fr."""
    await datagouv_service.refresh_all()
    return {
        "message": "Datasets refreshed",
        "status": datagouv_service.get_cache_status(),
    }


@router.post("/zone/analyze-enriched")
async def analyze_zone_enriched(
    data: ZoneAnalysisRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Analyse de zone enrichie avec données data.gouv.fr.
    Inclut: population, loyers, superficie, densité.
    """
    # Récupère toutes les communes avec coordonnées depuis data.gouv.fr
    all_communes = await datagouv_service.get_communes_with_data()

    communes_in_zone = []

    for commune in all_communes:
        lat = commune.get("latitude")
        lon = commune.get("longitude")
        if not lat or not lon:
            continue

        distance = haversine_distance(
            data.latitude, data.longitude,
            lat, lon
        )

        if distance <= data.radius_km:
            communes_in_zone.append({
                "code": commune.get("code"),
                "code_commune": commune.get("code"),
                "nom_commune": commune.get("nom"),
                "population": commune.get("population", 0),
                "latitude": lat,
                "longitude": lon,
                "superficie_km2": commune.get("superficie_km2"),
                "densite": commune.get("densite"),
                "distance_km": round(distance, 2),
            })

    # Enrichissement avec data.gouv.fr
    enrichment = await datagouv_service.enrich_zone_analysis(communes_in_zone)

    # Concurrents
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    brand_query = db.query(Advertiser).filter(Advertiser.is_active == True)
    if user:
        brand_query = brand_query.filter(Advertiser.id.in_(user_adv_ids))
    if x_advertiser_id:
        brand_query = brand_query.filter(Advertiser.id == int(x_advertiser_id))
    brand = brand_query.first()
    concurrents = []

    if brand:
        all_stores = db.query(Store).filter(
            Store.advertiser_id != brand.id,
            Store.latitude.isnot(None),
        ).all()

        for store in all_stores:
            distance = haversine_distance(
                data.latitude, data.longitude,
                store.latitude, store.longitude
            )
            if distance <= data.radius_km:
                concurrents.append({
                    "name": store.name,
                    "city": store.city,
                    "distance_km": round(distance, 2),
                })

    return {
        "center": {"latitude": data.latitude, "longitude": data.longitude},
        "radius_km": data.radius_km,
        "analysis": enrichment,
        "communes": sorted(communes_in_zone, key=lambda x: x["distance_km"]),
        "concurrents_proches": sorted(concurrents, key=lambda x: x["distance_km"]),
        "source": "data.gouv.fr (INSEE, Carte des loyers)",
    }

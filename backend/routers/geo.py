"""
Geo API router.
Gestion des magasins et analyses de zones de chalandise.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime
import csv
import io
import json

from database import get_db, Advertiser, Store, CommuneData, ZoneAnalysis, StoreLocation, Competitor
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

@router.get("/stores")
async def list_stores(
    department: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Liste les magasins de l'enseigne."""
    brand = db.query(Advertiser).filter(Advertiser.is_active == True).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Aucune enseigne configurée")

    query = db.query(Store).filter(
        Store.advertiser_id == brand.id,
        Store.is_active == True
    )

    if department:
        query = query.filter(Store.department == department)

    return query.all()


@router.post("/stores")
async def create_store(data: StoreCreate, db: Session = Depends(get_db)):
    """Ajoute un magasin."""
    brand = db.query(Advertiser).filter(Advertiser.is_active == True).first()
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
    db: Session = Depends(get_db)
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
    brand = db.query(Advertiser).filter(Advertiser.is_active == True).first()
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
    db: Session = Depends(get_db)
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
    brand = db.query(Advertiser).filter(Advertiser.is_active == True).first()
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
    db: Session = Depends(get_db)
):
    """
    Données pour affichage carte de France.

    Retourne les magasins et les données par commune
    pour superposition cartographique.
    """
    brand = db.query(Advertiser).filter(Advertiser.is_active == True).first()

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
):
    """Retourne les magasins concurrents groupés par concurrent.

    Par défaut ne renvoie que les comptages (léger).
    Passer include_stores=true pour obtenir le détail de chaque magasin (carte).
    """
    from sqlalchemy import func

    # Always get counts via aggregate query (lightweight)
    counts = (
        db.query(
            StoreLocation.competitor_id,
            func.count(StoreLocation.id).label("total"),
        )
        .filter(
            StoreLocation.source == "BANCO",
            StoreLocation.competitor_id.isnot(None),
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
                }
                for s in stores
            ]

        result.append(entry)

    return {
        "total_competitors": len(result),
        "total_stores": total_stores,
        "competitors": result,
    }


@router.get("/competitor-stores/{competitor_id}")
async def get_competitor_stores_geo(competitor_id: int, db: Session = Depends(get_db)):
    """Magasins d'un concurrent spécifique."""
    stores = db.query(StoreLocation).filter(
        StoreLocation.competitor_id == competitor_id,
        StoreLocation.source == "BANCO",
        StoreLocation.latitude.isnot(None),
    ).all()

    comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()

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


@router.post("/banco/enrich-all")
async def enrich_all_competitors(db: Session = Depends(get_db)):
    """Enrichit tous les concurrents existants avec la base commerces."""
    from services.banco import banco_service

    competitors = db.query(Competitor).filter(Competitor.is_active == True).all()
    results = []

    for comp in competitors:
        count = await banco_service.search_and_store(comp.id, comp.name, db)
        results.append({"competitor": comp.name, "stores_found": count})

    return {
        "message": f"{len(competitors)} concurrents enrichis",
        "results": results,
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
    db: Session = Depends(get_db)
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
    brand = db.query(Advertiser).filter(Advertiser.is_active == True).first()
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

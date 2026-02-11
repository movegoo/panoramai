"""
Router pour les layers cartographiques et POI.
Endpoints pour bornes IRVE, POI, limites administratives, etc.
"""
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException

from services.datagouv import datagouv_service

router = APIRouter(prefix="/api/layers", tags=["Map Layers"])


# =============================================================================
# Bornes de recharge IRVE
# =============================================================================

@router.get("/irve")
async def get_irve_stations(
    lat: Optional[float] = Query(None, description="Latitude du centre"),
    lng: Optional[float] = Query(None, description="Longitude du centre"),
    radius_km: float = Query(20, ge=1, le=100, description="Rayon de recherche en km"),
    department: Optional[str] = Query(None, description="Code département (ex: 75)"),
    limit: int = Query(200, ge=1, le=1000),
):
    """
    Récupère les bornes de recharge pour véhicules électriques.
    Filtrage par position + rayon ou par département.
    """
    stations = await datagouv_service.get_irve_stations(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        department=department,
    )
    return {
        "count": len(stations),
        "stations": stations[:limit],
        "filters": {
            "lat": lat,
            "lng": lng,
            "radius_km": radius_km if lat and lng else None,
            "department": department,
        },
    }


@router.get("/irve/stats")
async def get_irve_stats(
    department: Optional[str] = Query(None, description="Code département"),
):
    """
    Statistiques sur les bornes IRVE.
    """
    stations = await datagouv_service.get_irve_stations(department=department)

    total_stations = len(stations)
    total_points = sum(s.get("nb_points_charge", 1) for s in stations)
    puissance_moy = sum(s.get("puissance_max_kw", 0) for s in stations) / total_stations if total_stations else 0

    # Par opérateur
    by_operator = {}
    for s in stations:
        op = s.get("operateur") or "Inconnu"
        by_operator[op] = by_operator.get(op, 0) + 1

    top_operators = sorted(by_operator.items(), key=lambda x: x[1], reverse=True)[:10]

    # Accessibilité PMR
    pmr_count = sum(1 for s in stations if s.get("accessibilite_pmr"))
    gratuit_count = sum(1 for s in stations if s.get("gratuit"))

    return {
        "total_stations": total_stations,
        "total_points_charge": total_points,
        "puissance_moyenne_kw": round(puissance_moy, 1),
        "pct_accessibles_pmr": round(pmr_count / total_stations * 100, 1) if total_stations else 0,
        "pct_gratuit": round(gratuit_count / total_stations * 100, 1) if total_stations else 0,
        "top_operateurs": [{"operateur": op, "count": n} for op, n in top_operators],
    }


# =============================================================================
# Points d'intérêt (POI)
# =============================================================================

@router.get("/poi")
async def get_poi_nearby(
    lat: float = Query(..., description="Latitude du centre"),
    lng: float = Query(..., description="Longitude du centre"),
    radius_m: int = Query(1000, ge=100, le=5000, description="Rayon en mètres"),
    categories: Optional[str] = Query(
        None,
        description="Catégories séparées par virgules: restaurant,cafe,shop,hotel,pharmacy,bank,supermarket,bakery"
    ),
):
    """
    Récupère les points d'intérêt à proximité via OpenStreetMap.
    """
    cat_list = categories.split(",") if categories else None

    pois = await datagouv_service.get_poi_nearby(
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        categories=cat_list,
    )

    # Grouper par catégorie
    by_category = {}
    for poi in pois:
        cat = poi.get("category", "autre")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(poi)

    return {
        "count": len(pois),
        "pois": pois,
        "by_category": {k: len(v) for k, v in by_category.items()},
        "filters": {
            "lat": lat,
            "lng": lng,
            "radius_m": radius_m,
            "categories": cat_list,
        },
    }


# =============================================================================
# Île-de-France Mobilités
# =============================================================================

@router.get("/idf/covoiturage")
async def get_idf_carpooling(
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    radius_km: float = Query(30, ge=1, le=100),
):
    """
    Arrêts de covoiturage Île-de-France Mobilités.
    """
    stops = await datagouv_service.get_idf_carpooling_stops(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
    )
    return {
        "count": len(stops),
        "stops": stops,
    }


@router.get("/idf/velos/subventions")
async def get_idf_bike_subsidies():
    """
    Statistiques des subventions vélo en Île-de-France.
    """
    return await datagouv_service.get_idf_bike_subsidies()


@router.get("/idf/velos/parkings")
async def get_idf_bike_parkings():
    """
    Fréquentation des parkings vélos en Île-de-France.
    """
    parkings = await datagouv_service.get_idf_bike_parkings()
    return {
        "count": len(parkings),
        "parkings": parkings,
    }


# =============================================================================
# Contours géographiques
# =============================================================================

@router.get("/boundaries/{boundary_type}")
async def get_boundaries(
    boundary_type: str,
    code: Optional[str] = Query(None, description="Filtre par code (ex: 75 pour Paris)"),
):
    """
    Récupère les contours géographiques au format GeoJSON.
    Types: communes, departements, epci, academies
    """
    valid_types = ["communes", "departements", "regions", "epci", "academies"]
    if boundary_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Type invalide. Types valides: {', '.join(valid_types)}"
        )

    geojson = await datagouv_service.get_geojson_boundaries(
        boundary_type=boundary_type,
        code_filter=code,
    )

    return geojson


# =============================================================================
# Preload / cache GeoJSON boundaries
# =============================================================================

@router.post("/boundaries/preload")
async def preload_boundaries():
    """
    Pré-télécharge et cache en local tous les contours GeoJSON
    (régions, départements, EPCI, académies) pour un chargement rapide.
    """
    results = {}
    for boundary_type in ["regions", "departements", "epci", "academies"]:
        try:
            geojson = await datagouv_service.get_geojson_boundaries(boundary_type)
            count = len(geojson.get("features", []))
            results[boundary_type] = {"status": "ok", "features": count}
        except Exception as e:
            results[boundary_type] = {"status": "error", "error": str(e)}

    return {
        "message": "GeoJSON boundaries preloaded",
        "results": results,
    }


# =============================================================================
# Layer metadata
# =============================================================================

@router.get("/available")
async def get_available_layers():
    """
    Liste tous les layers disponibles avec leurs métadonnées.
    """
    return {
        "layers": [
            {
                "id": "irve",
                "name": "Bornes de recharge électrique",
                "description": "Bornes IRVE pour véhicules électriques",
                "icon": "zap",
                "color": "#22c55e",
                "endpoint": "/api/layers/irve",
                "filters": ["lat", "lng", "radius_km", "department"],
            },
            {
                "id": "poi",
                "name": "Points d'intérêt",
                "description": "Commerces, restaurants, services via OpenStreetMap",
                "icon": "map-pin",
                "color": "#f59e0b",
                "endpoint": "/api/layers/poi",
                "filters": ["lat", "lng", "radius_m", "categories"],
                "categories": ["restaurant", "cafe", "shop", "hotel", "pharmacy", "bank", "supermarket", "bakery"],
            },
            {
                "id": "idf_covoiturage",
                "name": "Covoiturage IDF",
                "description": "Arrêts de covoiturage Île-de-France Mobilités",
                "icon": "car",
                "color": "#8b5cf6",
                "endpoint": "/api/layers/idf/covoiturage",
                "region": "ile-de-france",
            },
            {
                "id": "regions",
                "name": "Régions",
                "description": "Contours des régions françaises (geo.api.gouv.fr)",
                "icon": "map",
                "color": "#8b5cf6",
                "endpoint": "/api/layers/boundaries/regions",
                "type": "boundary",
            },
            {
                "id": "departements",
                "name": "Départements",
                "description": "Contours des départements français (geo.api.gouv.fr)",
                "icon": "map",
                "color": "#3b82f6",
                "endpoint": "/api/layers/boundaries/departements",
                "type": "boundary",
            },
            {
                "id": "communes",
                "name": "Communes",
                "description": "Contours des communes françaises",
                "icon": "home",
                "color": "#6366f1",
                "endpoint": "/api/layers/boundaries/communes",
                "type": "boundary",
            },
            {
                "id": "epci",
                "name": "EPCI",
                "description": "Intercommunalités (EPCI)",
                "icon": "users",
                "color": "#ec4899",
                "endpoint": "/api/layers/boundaries/epci",
                "type": "boundary",
            },
            {
                "id": "academies",
                "name": "Académies",
                "description": "Académies scolaires",
                "icon": "graduation-cap",
                "color": "#14b8a6",
                "endpoint": "/api/layers/boundaries/academies",
                "type": "boundary",
            },
        ],
        "data_sources": [
            {"name": "data.gouv.fr", "url": "https://www.data.gouv.fr"},
            {"name": "geo.api.gouv.fr", "url": "https://geo.api.gouv.fr"},
            {"name": "Île-de-France Mobilités", "url": "https://data.iledefrance-mobilites.fr"},
            {"name": "OpenStreetMap", "url": "https://www.openstreetmap.org"},
        ],
    }

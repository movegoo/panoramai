"""
Service de données géographiques.
Intégration data.gouv.fr et INSEE pour analyses de zones.
"""
import httpx
import csv
import io
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

logger = logging.getLogger(__name__)


# =============================================================================
# Datasets data.gouv.fr
# =============================================================================

DATASETS = {
    "loyers": {
        "name": "Carte des loyers",
        "url": "https://www.data.gouv.fr/fr/datasets/r/f253d77c-3e49-4be1-b81b-ef75be2d6a80",
        "description": "Indicateurs de loyers d'annonce par commune",
    },
    "population": {
        "name": "Population par commune",
        "url": "https://www.data.gouv.fr/fr/datasets/r/f4e3c23e-9ab3-4e13-8db5-4f8bca0b4e9d",
        "description": "Population légale INSEE",
    },
    "equipements": {
        "name": "Base permanente des équipements",
        "url": "https://www.data.gouv.fr/fr/datasets/r/b56b5c94-6a35-4e7f-b1c2-78d8d8e9f8e2",
        "description": "Commerce, sport, services, santé",
    },
    "mobilite": {
        "name": "Déplacements domicile-travail",
        "url": "https://www.data.gouv.fr/fr/datasets/r/c3a3e5f6-8b7d-4e9a-b2c1-67f8e9d0a1b2",
        "description": "Modes de transport et distances",
    },
}


# =============================================================================
# Calculs géographiques
# =============================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule la distance en km entre deux points GPS.
    Formule de Haversine.
    """
    R = 6371  # Rayon de la Terre en km

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def get_bounding_box(lat: float, lon: float, radius_km: float) -> Dict[str, float]:
    """
    Retourne la bounding box pour une recherche rapide.
    Approximation: 1° lat ≈ 111 km, 1° lon ≈ 111 * cos(lat) km
    """
    lat_delta = radius_km / 111
    lon_delta = radius_km / (111 * cos(radians(lat)))

    return {
        "min_lat": lat - lat_delta,
        "max_lat": lat + lat_delta,
        "min_lon": lon - lon_delta,
        "max_lon": lon + lon_delta,
    }


# =============================================================================
# Service principal
# =============================================================================

class GeoDataService:
    """Service de données géographiques."""

    def __init__(self):
        self.cache = {}
        self.cache_expiry = {}

    async def fetch_csv(self, url: str, encoding: str = "utf-8") -> List[Dict]:
        """Télécharge et parse un CSV."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                content = response.content.decode(encoding)
                reader = csv.DictReader(io.StringIO(content), delimiter=";")
                return list(reader)

        except Exception as e:
            logger.error(f"Erreur fetch CSV {url}: {e}")
            return []

    async def get_loyers_data(self) -> List[Dict]:
        """Récupère les données de loyers par commune."""
        if "loyers" in self.cache:
            return self.cache["loyers"]

        data = await self.fetch_csv(DATASETS["loyers"]["url"])

        # Parse et normalise
        parsed = []
        for row in data:
            try:
                parsed.append({
                    "code_commune": row.get("code_commune", row.get("CODGEO", "")),
                    "nom_commune": row.get("nom_commune", row.get("LIBGEO", "")),
                    "loyer_moyen_m2": float(row.get("loyer_moyen", row.get("loypredm2", 0)) or 0),
                    "annee": row.get("annee", row.get("ANNEE", "2024")),
                })
            except (ValueError, TypeError):
                continue

        self.cache["loyers"] = parsed
        return parsed

    async def get_population_data(self) -> List[Dict]:
        """Récupère les données de population par commune."""
        if "population" in self.cache:
            return self.cache["population"]

        data = await self.fetch_csv(DATASETS["population"]["url"])

        parsed = []
        for row in data:
            try:
                parsed.append({
                    "code_commune": row.get("CODGEO", row.get("code_commune", "")),
                    "nom_commune": row.get("LIBGEO", row.get("nom_commune", "")),
                    "population": int(row.get("PMUN", row.get("population", 0)) or 0),
                    "annee": row.get("ANNEE", row.get("annee", "2021")),
                })
            except (ValueError, TypeError):
                continue

        self.cache["population"] = parsed
        return parsed

    async def get_equipements_data(self, code_postal: str = None) -> List[Dict]:
        """Récupère les données d'équipements (commerces, services)."""
        # Cette API retourne beaucoup de données, on peut filtrer par CP
        if f"equipements_{code_postal}" in self.cache:
            return self.cache[f"equipements_{code_postal}"]

        data = await self.fetch_csv(DATASETS["equipements"]["url"])

        parsed = []
        for row in data:
            if code_postal and row.get("DEPCOM", "")[:5] != code_postal:
                continue

            try:
                parsed.append({
                    "code_commune": row.get("DEPCOM", ""),
                    "type_equipement": row.get("TYPEQU", ""),
                    "nom_equipement": row.get("NOMQU", ""),
                    "latitude": float(row.get("LATITUDE", 0) or 0),
                    "longitude": float(row.get("LONGITUDE", 0) or 0),
                })
            except (ValueError, TypeError):
                continue

        self.cache[f"equipements_{code_postal}"] = parsed
        return parsed

    def analyze_zone(
        self,
        center_lat: float,
        center_lon: float,
        radius_km: float,
        communes_data: List[Dict],
    ) -> Dict[str, Any]:
        """
        Analyse une zone de chalandise autour d'un point.

        Args:
            center_lat: Latitude du centre (magasin)
            center_lon: Longitude du centre
            radius_km: Rayon de la zone en km
            communes_data: Données des communes avec lat/lon

        Returns:
            Agrégats de la zone
        """
        bbox = get_bounding_box(center_lat, center_lon, radius_km)

        communes_in_zone = []
        for commune in communes_data:
            lat = commune.get("latitude")
            lon = commune.get("longitude")

            if not lat or not lon:
                continue

            # Filtre rapide par bounding box
            if not (bbox["min_lat"] <= lat <= bbox["max_lat"] and
                    bbox["min_lon"] <= lon <= bbox["max_lon"]):
                continue

            # Vérification précise par distance
            distance = haversine_distance(center_lat, center_lon, lat, lon)
            if distance <= radius_km:
                commune["distance_km"] = round(distance, 2)
                communes_in_zone.append(commune)

        # Agrégations
        total_population = sum(c.get("population", 0) for c in communes_in_zone)
        loyers = [c.get("loyer_moyen_m2") for c in communes_in_zone if c.get("loyer_moyen_m2")]
        revenus = [c.get("revenu_median") for c in communes_in_zone if c.get("revenu_median")]

        return {
            "center": {"latitude": center_lat, "longitude": center_lon},
            "radius_km": radius_km,
            "nb_communes": len(communes_in_zone),
            "population_totale": total_population,
            "loyer_moyen_m2": round(sum(loyers) / len(loyers), 2) if loyers else None,
            "revenu_median_moyen": round(sum(revenus) / len(revenus), 2) if revenus else None,
            "communes": sorted(communes_in_zone, key=lambda x: x.get("distance_km", 999))[:20],
        }


# Singleton
geodata_service = GeoDataService()


# =============================================================================
# Données de référence communes françaises
# =============================================================================

# Top 50 communes par population avec coordonnées GPS
COMMUNES_REFERENCE = [
    {"code": "75056", "nom": "Paris", "lat": 48.8566, "lon": 2.3522, "pop": 2148000, "dep": "75"},
    {"code": "13055", "nom": "Marseille", "lat": 43.2965, "lon": 5.3698, "pop": 870000, "dep": "13"},
    {"code": "69123", "nom": "Lyon", "lat": 45.7640, "lon": 4.8357, "pop": 522000, "dep": "69"},
    {"code": "31555", "nom": "Toulouse", "lat": 43.6047, "lon": 1.4442, "pop": 493000, "dep": "31"},
    {"code": "06088", "nom": "Nice", "lat": 43.7102, "lon": 7.2620, "pop": 342000, "dep": "06"},
    {"code": "44109", "nom": "Nantes", "lat": 47.2184, "lon": -1.5536, "pop": 320000, "dep": "44"},
    {"code": "67482", "nom": "Strasbourg", "lat": 48.5734, "lon": 7.7521, "pop": 287000, "dep": "67"},
    {"code": "33063", "nom": "Bordeaux", "lat": 44.8378, "lon": -0.5792, "pop": 260000, "dep": "33"},
    {"code": "59350", "nom": "Lille", "lat": 50.6292, "lon": 3.0573, "pop": 236000, "dep": "59"},
    {"code": "35238", "nom": "Rennes", "lat": 48.1173, "lon": -1.6778, "pop": 222000, "dep": "35"},
    {"code": "51454", "nom": "Reims", "lat": 49.2583, "lon": 4.0317, "pop": 182000, "dep": "51"},
    {"code": "76540", "nom": "Le Havre", "lat": 49.4944, "lon": 0.1079, "pop": 172000, "dep": "76"},
    {"code": "42218", "nom": "Saint-Étienne", "lat": 45.4397, "lon": 4.3872, "pop": 172000, "dep": "42"},
    {"code": "83137", "nom": "Toulon", "lat": 43.1242, "lon": 5.9280, "pop": 171000, "dep": "83"},
    {"code": "38185", "nom": "Grenoble", "lat": 45.1885, "lon": 5.7245, "pop": 158000, "dep": "38"},
    {"code": "21231", "nom": "Dijon", "lat": 47.3220, "lon": 5.0415, "pop": 157000, "dep": "21"},
    {"code": "49007", "nom": "Angers", "lat": 47.4784, "lon": -0.5632, "pop": 155000, "dep": "49"},
    {"code": "30189", "nom": "Nîmes", "lat": 43.8367, "lon": 4.3601, "pop": 151000, "dep": "30"},
    {"code": "63113", "nom": "Clermont-Ferrand", "lat": 45.7772, "lon": 3.0870, "pop": 147000, "dep": "63"},
    {"code": "34172", "nom": "Montpellier", "lat": 43.6108, "lon": 3.8767, "pop": 290000, "dep": "34"},
]


def get_communes_by_department(department: str) -> List[Dict]:
    """Retourne les communes d'un département."""
    return [c for c in COMMUNES_REFERENCE if c["dep"] == department]


def find_nearest_commune(lat: float, lon: float) -> Dict:
    """Trouve la commune la plus proche d'un point."""
    nearest = None
    min_distance = float("inf")

    for commune in COMMUNES_REFERENCE:
        distance = haversine_distance(lat, lon, commune["lat"], commune["lon"])
        if distance < min_distance:
            min_distance = distance
            nearest = commune

    if nearest:
        nearest["distance_km"] = round(min_distance, 2)

    return nearest

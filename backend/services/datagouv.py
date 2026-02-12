"""
Service d'intégration data.gouv.fr
Téléchargement, cache et parsing des datasets publics pour l'analyse de zones.
"""
import csv
import io
import json
import logging
import httpx
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from core.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration des datasets
# =============================================================================

DATASETS = {
    # === Communes & Population ===
    "communes_geo": {
        "name": "Communes avec coordonnées GPS",
        "url": "https://www.data.gouv.fr/fr/datasets/r/dbe8a621-a9c4-4bc3-9cae-be1699c5ff25",
        "delimiter": ",",
        "encoding": "utf-8",
    },
    "communes_2025": {
        "name": "Communes et villes de France 2025 (avec population)",
        "url": "https://www.data.gouv.fr/api/1/datasets/r/f5df602b-3800-44d7-b2df-fa40a0350325",
        "delimiter": ",",
        "encoding": "utf-8",
    },

    # === Loyers ===
    "loyers_appartements": {
        "name": "Carte des loyers appartements par commune 2022",
        "url": "https://www.data.gouv.fr/api/1/datasets/r/bc9d5d13-07cc-4d38-8254-88db065bd42b",
        "delimiter": ";",
        "encoding": "utf-8",
    },
    "loyers_maisons": {
        "name": "Carte des loyers maisons par commune 2022",
        "url": "https://www.data.gouv.fr/api/1/datasets/r/dfb542cd-a808-41e2-9157-8d39b5c24edb",
        "delimiter": ";",
        "encoding": "utf-8",
    },

    # === Mobilité / Transport ===
    "flux_domicile_travail": {
        "name": "Flux domicile-travail par mode de transport (commune)",
        "url": "https://www.data.gouv.fr/api/1/datasets/r/f624e1db-8f22-4a96-9f5a-9f9ee2aae53e",
        "delimiter": ",",
        "encoding": "utf-8",
    },

    # === Revenus & Pauvreté ===
    "revenus_carroyes_2019": {
        "name": "Revenus, pauvreté et niveau de vie - données carroyées 2019",
        "url": "https://www.data.gouv.fr/api/1/datasets/r/60b30038-0649-460a-ac69-03142d0ff282",
        "delimiter": ";",
        "encoding": "utf-8",
    },
    "revenus_menages_2022": {
        "name": "Indicateurs de revenu disponible ménages 2022",
        "url": "https://api.insee.fr/melodi/file/DS_ERFS_MENAGE/DS_ERFS_MENAGE_2022_CSV_FR",
        "delimiter": ";",
        "encoding": "utf-8",
        "is_zip": True,
    },

    # === Données socio-démographiques INSEE (Base dossier complet) ===
    "insee_socio_demo": {
        "name": "Base INSEE dossier complet - données socio-démographiques communales",
        "url": "https://www.insee.fr/fr/statistiques/fichier/5359146/dossier_complet.zip",
        "delimiter": ";",
        "encoding": "utf-8",
        "is_zip": True,
        "zip_file": "dossier_complet.csv",
    },

    # === Bornes de recharge électriques (IRVE) - Base nationale consolidée ===
    "irve_bornes": {
        "name": "Bornes de recharge pour véhicules électriques (consolidation nationale)",
        "url": "https://www.data.gouv.fr/api/1/datasets/r/eb76d20a-8501-400e-b336-d85724de5435",
        "delimiter": ",",
        "encoding": "utf-8",
    },

    # === Île-de-France Mobilités ===
    "idf_subventions_velo": {
        "name": "Subventions achat vélo Île-de-France",
        "url": "https://www.data.gouv.fr/api/1/datasets/r/8176b6d5-5273-4c9d-8a6f-7fc0b90a81bb",
        "delimiter": ",",
        "encoding": "utf-8",
    },
    "idf_parkings_velos": {
        "name": "Fréquentation parkings vélos IDF",
        "url": "https://www.data.gouv.fr/api/1/datasets/r/93b40dca-b138-4034-867f-e1904bfd264d",
        "delimiter": ",",
        "encoding": "utf-8",
    },
    "idf_covoiturage": {
        "name": "Arrêts de covoiturage Île-de-France Mobilités",
        "url": "https://www.data.gouv.fr/api/1/datasets/r/bef408e6-0440-4eab-82a9-671ec96f09df",
        "delimiter": ",",
        "encoding": "utf-8",
    },
}

# === GeoJSON datasets (fetched separately) ===
GEOJSON_DATASETS = {
    "communes_contours": {
        "name": "Contours communes France",
        "url": "https://object.data.gouv.fr/contours-administratifs/2025/geojson/communes-100m.geojson",
    },
    "departements_contours": {
        "name": "Contours départements France",
        "url": "https://object.data.gouv.fr/contours-administratifs/2025/geojson/departements-100m.geojson",
    },
    "regions_contours": {
        "name": "Contours régions France",
        "url": "https://object.data.gouv.fr/contours-administratifs/2025/geojson/regions-100m.geojson",
    },
    "epci_contours": {
        "name": "Contours EPCI France",
        "url": "https://object.data.gouv.fr/contours-administratifs/2025/geojson/epci-100m.geojson",
    },
    "academies_contours": {
        "name": "Contours académies France",
        "url": "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-contour-academies-2020/exports/geojson",
    },
}

# Codes équipements BPE commerce
EQUIPEMENTS_COMMERCE = {
    "B101": "Hypermarché",
    "B102": "Supermarché",
    "B103": "Grande surface de bricolage",
    "B201": "Supérette",
    "B202": "Épicerie",
    "B203": "Boulangerie",
    "B301": "Librairie papeterie",
    "B302": "Magasin de vêtements",
    "B304": "Magasin de chaussures",
    "B305": "Magasin d'électroménager",
    "B306": "Magasin de meubles",
    "B307": "Magasin d'articles de sports",
    "B316": "Station service",
}


import os

# Max rows to load into memory per dataset (prevents OOM on 512MB Render)
MAX_DATASET_ROWS = int(os.getenv("MAX_DATASET_ROWS", "50000"))
# Datasets too large for low-memory environments (skip unless explicitly requested)
HEAVY_DATASETS = {"insee_socio_demo", "irve_bornes"}


class DataGouvService:
    """Service de téléchargement et cache des données data.gouv.fr."""

    def __init__(self):
        self.cache_dir = settings.DATAGOUV_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Cache Management
    # =========================================================================

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _is_cache_valid(self, key: str) -> bool:
        path = self._cache_path(key)
        if not path.exists():
            return False
        cache_time = datetime.fromtimestamp(path.stat().st_mtime)
        expiry = datetime.now() - timedelta(days=settings.DATAGOUV_CACHE_DAYS)
        return cache_time > expiry

    def _read_cache(self, key: str) -> Optional[List[Dict]]:
        path = self._cache_path(key)
        if path.exists():
            # Skip files > 100MB to avoid OOM
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > 100:
                logger.warning(f"Cache file '{key}' too large ({size_mb:.0f}MB), skipping to avoid OOM")
                return None
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Cache read error {key}: {e}")
        return None

    def _write_cache(self, key: str, data: List[Dict]):
        path = self._cache_path(key)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            logger.info(f"Cache saved: {key} ({len(data)} rows)")
        except Exception as e:
            logger.error(f"Cache write error {key}: {e}")

    # =========================================================================
    # CSV Download & Parse
    # =========================================================================

    async def _fetch_csv(
        self,
        url: str,
        delimiter: str = ";",
        encoding: str = "utf-8",
    ) -> List[Dict]:
        """Télécharge et parse un CSV."""
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Essaie plusieurs encodages
                content = None
                for enc in [encoding, "utf-8", "latin-1", "cp1252"]:
                    try:
                        content = response.content.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue

                if not content:
                    logger.error(f"Cannot decode CSV: {url}")
                    return []

                reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
                return list(reader)

        except Exception as e:
            logger.error(f"CSV fetch error {url}: {e}")
            return []

    async def fetch_dataset(
        self,
        dataset_key: str,
        force_refresh: bool = False,
    ) -> List[Dict]:
        """Télécharge un dataset avec cache."""
        if dataset_key not in DATASETS:
            logger.warning(f"Unknown dataset: {dataset_key}")
            return []

        # Skip heavy datasets on low-memory environments
        if dataset_key in HEAVY_DATASETS:
            logger.warning(f"Skipping heavy dataset '{dataset_key}' to avoid OOM (set MAX_DATASET_ROWS higher to override)")
            return []

        # Check cache
        if not force_refresh and self._is_cache_valid(dataset_key):
            cached = self._read_cache(dataset_key)
            if cached:
                logger.info(f"Loaded from cache: {dataset_key} ({len(cached)} rows)")
                return cached

        # Download
        config = DATASETS[dataset_key]
        logger.info(f"Downloading: {config['name']}")

        # Handle ZIP files
        if config.get("is_zip"):
            data = await self._fetch_csv_from_zip(
                url=config["url"],
                zip_file=config.get("zip_file"),
                delimiter=config.get("delimiter", ";"),
                encoding=config.get("encoding", "utf-8"),
            )
        else:
            data = await self._fetch_csv(
                url=config["url"],
                delimiter=config.get("delimiter", ";"),
                encoding=config.get("encoding", "utf-8"),
            )

        # Truncate to prevent OOM
        if len(data) > MAX_DATASET_ROWS:
            logger.warning(f"Dataset '{dataset_key}' truncated from {len(data)} to {MAX_DATASET_ROWS} rows")
            data = data[:MAX_DATASET_ROWS]

        if data:
            self._write_cache(dataset_key, data)

        return data

    async def _fetch_csv_from_zip(
        self,
        url: str,
        zip_file: Optional[str] = None,
        delimiter: str = ";",
        encoding: str = "utf-8",
    ) -> List[Dict]:
        """Télécharge et parse un CSV depuis un fichier ZIP."""
        import zipfile

        try:
            async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
                logger.info(f"Downloading ZIP: {url}")
                response = await client.get(url)
                response.raise_for_status()

                # Extract CSV from ZIP
                with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                    # Find CSV file
                    csv_files = [f for f in zf.namelist() if f.endswith('.csv')]
                    if zip_file and zip_file in zf.namelist():
                        target_file = zip_file
                    elif csv_files:
                        target_file = csv_files[0]
                    else:
                        logger.error(f"No CSV file found in ZIP: {url}")
                        return []

                    logger.info(f"Extracting: {target_file}")
                    content = None
                    raw_content = zf.read(target_file)

                    for enc in [encoding, "utf-8", "latin-1", "cp1252"]:
                        try:
                            content = raw_content.decode(enc)
                            break
                        except UnicodeDecodeError:
                            continue

                    if not content:
                        logger.error(f"Cannot decode CSV from ZIP: {url}")
                        return []

                    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
                    return list(reader)

        except Exception as e:
            logger.error(f"ZIP fetch error {url}: {e}")
            return []

    # =========================================================================
    # Données communes enrichies
    # =========================================================================

    async def get_communes_with_data(
        self,
        department: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """
        Récupère les communes avec population, coordonnées GPS.
        Utilise le dataset communes_2025 qui contient tout.
        Fallback sur données locales si non disponible.
        """
        # Charge le dataset communes 2025 (inclut population + coordonnées)
        communes_data = await self.fetch_dataset("communes_2025")

        result = []

        if communes_data:
            for row in communes_data:
                try:
                    # Code INSEE commune (colonnes réelles du dataset)
                    code = row.get("code_insee") or row.get("COM") or ""
                    if not code:
                        continue

                    # Département
                    dep = row.get("dep_code") or (code[:2] if len(code) >= 2 else "")
                    if code.startswith("97"):
                        dep = code[:3]

                    if department and dep != department:
                        continue

                    # Population
                    pop_str = row.get("population") or "0"
                    try:
                        pop = int(float(str(pop_str).replace(" ", "").replace(",", ".")))
                    except (ValueError, TypeError):
                        pop = 0

                    # Coordonnées (latitude/longitude centre ou mairie)
                    lat_str = row.get("latitude_centre") or row.get("latitude_mairie")
                    lng_str = row.get("longitude_centre") or row.get("longitude_mairie")

                    try:
                        lat = float(lat_str) if lat_str else None
                        lng = float(lng_str) if lng_str else None
                    except (ValueError, TypeError):
                        lat, lng = None, None

                    # Nom
                    nom = row.get("nom_standard") or row.get("nom_sans_pronom") or ""

                    # Superficie
                    sup_str = row.get("superficie_km2") or "0"
                    try:
                        superficie = float(str(sup_str).replace(",", "."))
                    except (ValueError, TypeError):
                        superficie = None

                    # Densité
                    dens_str = row.get("densite") or "0"
                    try:
                        densite = float(str(dens_str).replace(",", "."))
                    except (ValueError, TypeError):
                        densite = None

                    result.append({
                        "code": code,
                        "nom": nom,
                        "department": dep,
                        "population": pop,
                        "latitude": lat,
                        "longitude": lng,
                        "superficie_km2": superficie,
                        "densite": densite,
                        "code_postal": row.get("code_postal"),
                        "epci": row.get("epci_nom"),
                    })
                except Exception as e:
                    logger.debug(f"Error parsing commune: {e}")
                    continue

        if not result:
            # Fallback données locales (top 100 communes)
            result = self._get_fallback_communes()
            if department:
                result = [c for c in result if c.get("department") == department]

        # Tri par population décroissante
        result.sort(key=lambda x: x.get("population", 0), reverse=True)

        if limit:
            result = result[:limit]

        return result

    def _get_fallback_communes(self) -> List[Dict]:
        """Données de secours - top 100 communes françaises."""
        return [
            {"code": "75056", "nom": "Paris", "department": "75", "latitude": 48.8566, "longitude": 2.3522, "population": 2148000},
            {"code": "13055", "nom": "Marseille", "department": "13", "latitude": 43.2965, "longitude": 5.3698, "population": 870000},
            {"code": "69123", "nom": "Lyon", "department": "69", "latitude": 45.7640, "longitude": 4.8357, "population": 522000},
            {"code": "31555", "nom": "Toulouse", "department": "31", "latitude": 43.6047, "longitude": 1.4442, "population": 493000},
            {"code": "06088", "nom": "Nice", "department": "06", "latitude": 43.7102, "longitude": 7.2620, "population": 342000},
            {"code": "44109", "nom": "Nantes", "department": "44", "latitude": 47.2184, "longitude": -1.5536, "population": 320000},
            {"code": "34172", "nom": "Montpellier", "department": "34", "latitude": 43.6108, "longitude": 3.8767, "population": 290000},
            {"code": "67482", "nom": "Strasbourg", "department": "67", "latitude": 48.5734, "longitude": 7.7521, "population": 287000},
            {"code": "33063", "nom": "Bordeaux", "department": "33", "latitude": 44.8378, "longitude": -0.5792, "population": 260000},
            {"code": "59350", "nom": "Lille", "department": "59", "latitude": 50.6292, "longitude": 3.0573, "population": 236000},
            {"code": "35238", "nom": "Rennes", "department": "35", "latitude": 48.1173, "longitude": -1.6778, "population": 222000},
            {"code": "51454", "nom": "Reims", "department": "51", "latitude": 49.2583, "longitude": 4.0317, "population": 182000},
            {"code": "76540", "nom": "Le Havre", "department": "76", "latitude": 49.4944, "longitude": 0.1079, "population": 172000},
            {"code": "42218", "nom": "Saint-Étienne", "department": "42", "latitude": 45.4397, "longitude": 4.3872, "population": 172000},
            {"code": "83137", "nom": "Toulon", "department": "83", "latitude": 43.1242, "longitude": 5.9280, "population": 171000},
            {"code": "38185", "nom": "Grenoble", "department": "38", "latitude": 45.1885, "longitude": 5.7245, "population": 158000},
            {"code": "21231", "nom": "Dijon", "department": "21", "latitude": 47.3220, "longitude": 5.0415, "population": 157000},
            {"code": "49007", "nom": "Angers", "department": "49", "latitude": 47.4784, "longitude": -0.5632, "population": 155000},
            {"code": "30189", "nom": "Nîmes", "department": "30", "latitude": 43.8367, "longitude": 4.3601, "population": 151000},
            {"code": "63113", "nom": "Clermont-Ferrand", "department": "63", "latitude": 45.7772, "longitude": 3.0870, "population": 147000},
            {"code": "13001", "nom": "Aix-en-Provence", "department": "13", "latitude": 43.5297, "longitude": 5.4474, "population": 145000},
            {"code": "72181", "nom": "Le Mans", "department": "72", "latitude": 48.0061, "longitude": 0.1996, "population": 144000},
            {"code": "29019", "nom": "Brest", "department": "29", "latitude": 48.3904, "longitude": -4.4861, "population": 140000},
            {"code": "37261", "nom": "Tours", "department": "37", "latitude": 47.3941, "longitude": 0.6848, "population": 137000},
            {"code": "80021", "nom": "Amiens", "department": "80", "latitude": 49.8941, "longitude": 2.2958, "population": 135000},
            {"code": "87085", "nom": "Limoges", "department": "87", "latitude": 45.8336, "longitude": 1.2611, "population": 133000},
            {"code": "68066", "nom": "Mulhouse", "department": "68", "latitude": 47.7508, "longitude": 7.3359, "population": 109000},
            {"code": "66136", "nom": "Perpignan", "department": "66", "latitude": 42.6986, "longitude": 2.8956, "population": 121000},
            {"code": "25056", "nom": "Besançon", "department": "25", "latitude": 47.2378, "longitude": 6.0241, "population": 118000},
            {"code": "76351", "nom": "Rouen", "department": "76", "latitude": 49.4432, "longitude": 1.0993, "population": 113000},
            {"code": "45234", "nom": "Orléans", "department": "45", "latitude": 47.9029, "longitude": 1.9093, "population": 116000},
            {"code": "14118", "nom": "Caen", "department": "14", "latitude": 49.1829, "longitude": -0.3707, "population": 108000},
            {"code": "57463", "nom": "Metz", "department": "57", "latitude": 49.1193, "longitude": 6.1757, "population": 119000},
            {"code": "59512", "nom": "Roubaix", "department": "59", "latitude": 50.6942, "longitude": 3.1746, "population": 98000},
            {"code": "54395", "nom": "Nancy", "department": "54", "latitude": 48.6921, "longitude": 6.1844, "population": 105000},
            {"code": "93008", "nom": "Bondy", "department": "93", "latitude": 48.9022, "longitude": 2.4828, "population": 53000},
            {"code": "93048", "nom": "Montreuil", "department": "93", "latitude": 48.8638, "longitude": 2.4483, "population": 109000},
            {"code": "92012", "nom": "Boulogne-Billancourt", "department": "92", "latitude": 48.8352, "longitude": 2.2409, "population": 121000},
            {"code": "92044", "nom": "Levallois-Perret", "department": "92", "latitude": 48.8933, "longitude": 2.2872, "population": 66000},
            {"code": "94028", "nom": "Créteil", "department": "94", "latitude": 48.7904, "longitude": 2.4556, "population": 92000},
        ]

    async def get_loyers_data(
        self,
        department: Optional[str] = None,
        type_bien: str = "appartement",
    ) -> List[Dict]:
        """
        Récupère les données de loyers par commune.

        Args:
            department: Filtrer par département
            type_bien: "appartement" ou "maison"
        """
        dataset_key = "loyers_maisons" if type_bien == "maison" else "loyers_appartements"
        data = await self.fetch_dataset(dataset_key)

        result = []
        for row in data:
            try:
                # Code commune INSEE (colonne réelle: INSEE_C)
                code = row.get("INSEE_C") or row.get("CODGEO") or ""
                if not code:
                    continue

                # Département (colonne réelle: DEP)
                dep = row.get("DEP") or (code[:2] if len(code) >= 2 else "")
                if code.startswith("97"):
                    dep = code[:3]

                if department and dep != department:
                    continue

                # Loyer prédit au m² (colonne réelle: loypredm2)
                loyer_str = row.get("loypredm2") or "0"
                loyer = float(str(loyer_str).replace(",", ".")) if loyer_str else 0

                if loyer <= 0:
                    continue

                # Type de prédiction (TYPPRED)
                type_pred = row.get("TYPPRED", "")

                result.append({
                    "code_commune": code,
                    "nom_commune": row.get("LIBGEO", ""),
                    "loyer_m2": round(loyer, 2),
                    "type_prediction": type_pred,
                    "type_bien": type_bien,
                })
            except (ValueError, TypeError) as e:
                logger.debug(f"Error parsing loyer row: {e}")
                continue

        return result

    async def get_revenus_data(self, department: Optional[str] = None) -> List[Dict]:
        """
        Récupère les données de revenus carroyées 2019 (Filosofi).
        """
        data = await self.fetch_dataset("revenus_carroyes_2019")

        result = []
        for row in data:
            try:
                # Les données carroyées utilisent un identifiant de carreau
                code = row.get("idcar_200m") or row.get("idcar_1km") or row.get("CODGEO") or ""
                if not code:
                    continue

                # Revenu médian
                revenu_str = row.get("ind_snv") or row.get("revenu_median") or row.get("Q2") or "0"
                revenu = float(str(revenu_str).replace(",", ".")) if revenu_str else 0

                # Taux de pauvreté
                pauvrete_str = row.get("men_pauv") or row.get("taux_pauvrete") or "0"

                if revenu > 0:
                    result.append({
                        "code": code,
                        "revenu_median": round(revenu, 0),
                        "taux_pauvrete": float(str(pauvrete_str).replace(",", ".")) if pauvrete_str else None,
                    })
            except (ValueError, TypeError):
                continue

        return result

    async def get_transport_data(self, department: Optional[str] = None) -> List[Dict]:
        """
        Récupère les données de flux domicile-travail par mode de transport.
        Format long: une ligne par commune/mode de transport.
        Valeurs = effectifs absolus (nombre de personnes).
        """
        data = await self.fetch_dataset("flux_domicile_travail")

        # Pivot: groupe par commune (effectifs absolus)
        communes_transport: Dict[str, Dict[str, float]] = {}

        for row in data:
            try:
                code = row.get("geocode_commune") or row.get("CODGEO") or ""
                if not code:
                    continue

                mode = row.get("mode_transport", "").lower()
                valeur_str = row.get("valeur", "0")
                valeur = float(str(valeur_str).replace(",", ".")) if valeur_str else 0

                if code not in communes_transport:
                    communes_transport[code] = {
                        "nom": row.get("libelle_commune", ""),
                        "voiture": 0,
                        "transport_commun": 0,
                        "velo": 0,
                        "marche": 0,
                        "autre": 0,
                    }

                # Map mode to category
                if "voiture" in mode:
                    communes_transport[code]["voiture"] += valeur
                elif "commun" in mode:
                    communes_transport[code]["transport_commun"] += valeur
                elif "vélo" in mode:
                    communes_transport[code]["velo"] += valeur
                elif "deux-roues" in mode or "2 roues" in mode:
                    communes_transport[code]["velo"] += valeur  # Inclut 2 roues motorisés dans vélo
                elif "marche" in mode or "pied" in mode:
                    communes_transport[code]["marche"] += valeur
                else:
                    communes_transport[code]["autre"] += valeur

            except (ValueError, TypeError) as e:
                logger.debug(f"Error parsing transport row: {e}")
                continue

        # Build result avec calcul des pourcentages
        result = []
        for code, modes in communes_transport.items():
            dep = code[:2] if len(code) >= 2 else ""
            if code.startswith("97"):
                dep = code[:3]

            if department and dep != department:
                continue

            # Total = sum of all modes (effectifs absolus)
            total = modes["voiture"] + modes["transport_commun"] + modes["velo"] + modes["marche"] + modes["autre"]

            if total > 0:
                result.append({
                    "code_commune": code,
                    "nom_commune": modes["nom"],
                    "actifs_total": int(total),
                    "pct_voiture": round(modes["voiture"] / total * 100, 1),
                    "pct_transport_commun": round(modes["transport_commun"] / total * 100, 1),
                    "pct_velo_2roues": round(modes["velo"] / total * 100, 1),
                    "pct_marche": round(modes["marche"] / total * 100, 1),
                })

        return result

    # =========================================================================
    # Zone Analysis Enrichment
    # =========================================================================

    async def enrich_zone_analysis(
        self,
        communes: List[Dict],
    ) -> Dict[str, Any]:
        """
        Enrichit une analyse de zone avec les données data.gouv.fr.

        Args:
            communes: Liste de communes avec au moins 'code' ou 'code_commune'

        Returns:
            Statistiques agrégées pour la zone
        """
        if not communes:
            return {}

        # Récupère les données
        loyers_appart = await self.get_loyers_data(type_bien="appartement")
        loyers_maison = await self.get_loyers_data(type_bien="maison")
        transport_data = await self.get_transport_data()

        # Index par code commune
        loyers_appart_idx = {l["code_commune"]: l["loyer_m2"] for l in loyers_appart}
        loyers_maison_idx = {l["code_commune"]: l["loyer_m2"] for l in loyers_maison}
        transport_idx = {t["code_commune"]: t for t in transport_data}

        # Enrichit et agrège
        total_pop = 0
        total_superficie = 0
        total_actifs = 0
        loyers_appart_list = []
        loyers_maison_list = []

        # Transport aggregates (weighted by population)
        transport_voiture = 0
        transport_commun = 0
        transport_velo = 0
        transport_marche = 0
        communes_with_transport = 0

        for commune in communes:
            code = commune.get("code") or commune.get("code_commune", "")
            pop = commune.get("population", 0)
            total_pop += pop

            superficie = commune.get("superficie_km2", 0) or 0
            total_superficie += superficie

            # Loyers
            if code in loyers_appart_idx:
                commune["loyer_m2_appartement"] = loyers_appart_idx[code]
                loyers_appart_list.append(loyers_appart_idx[code])

            if code in loyers_maison_idx:
                commune["loyer_m2_maison"] = loyers_maison_idx[code]
                loyers_maison_list.append(loyers_maison_idx[code])

            # Transport (pondéré par nombre d'actifs réels)
            if code in transport_idx:
                t = transport_idx[code]
                actifs = t.get("actifs_total", 0)
                communes_with_transport += 1
                total_actifs += actifs
                # Reconvertir les pourcentages en effectifs pour la somme
                transport_voiture += actifs * t.get("pct_voiture", 0) / 100
                transport_commun += actifs * t.get("pct_transport_commun", 0) / 100
                transport_velo += actifs * t.get("pct_velo_2roues", 0) / 100
                transport_marche += actifs * t.get("pct_marche", 0) / 100

        # Moyennes
        avg_loyer_appart = sum(loyers_appart_list) / len(loyers_appart_list) if loyers_appart_list else None
        avg_loyer_maison = sum(loyers_maison_list) / len(loyers_maison_list) if loyers_maison_list else None

        # Densité moyenne de la zone
        densite_zone = total_pop / total_superficie if total_superficie > 0 else None

        # Transport moyens pondérés par population
        transport_stats = None
        if total_actifs > 0 and communes_with_transport > 0:
            transport_stats = {
                "communes_couvertes": communes_with_transport,
                "pct_voiture": round(transport_voiture / total_actifs * 100, 1),
                "pct_transport_commun": round(transport_commun / total_actifs * 100, 1),
                "pct_velo_2roues": round(transport_velo / total_actifs * 100, 1),
                "pct_marche": round(transport_marche / total_actifs * 100, 1),
            }

        # Socio-démographique (agrégation pondérée par population)
        socio_demo = await self._aggregate_socio_demo(communes)

        return {
            "population_totale": total_pop,
            "superficie_totale_km2": round(total_superficie, 2) if total_superficie else None,
            "densite_moyenne": round(densite_zone, 1) if densite_zone else None,
            "nb_communes": len(communes),
            "loyer_moyen_m2_appartement": round(avg_loyer_appart, 2) if avg_loyer_appart else None,
            "loyer_moyen_m2_maison": round(avg_loyer_maison, 2) if avg_loyer_maison else None,
            "communes_avec_loyers": len(loyers_appart_list) + len(loyers_maison_list),
            "mobilite": transport_stats,
            "socio_demo": socio_demo,
        }

    async def _aggregate_socio_demo(self, communes: List[Dict]) -> Optional[Dict]:
        """Agrège les données socio-démographiques pour une liste de communes."""
        commune_codes = [c.get("code") or c.get("code_commune", "") for c in communes]
        socio_data = await self.get_socio_demo_data(commune_codes)

        if not socio_data:
            return None

        # Agrégation pondérée par population
        total_pop = 0
        total_hommes = 0
        total_femmes = 0
        age_totals = {"0-14": 0, "15-29": 0, "30-44": 0, "45-59": 0, "60-74": 0, "75+": 0}
        chomeurs_total = 0
        actifs_total = 0
        proprietaires_total = 0
        menages_total = 0
        revenus_list = []
        pauvrete_list = []
        csp_totals = {"cadres": 0, "prof_intermediaires": 0, "employes": 0, "ouvriers": 0, "retraites": 0}
        communes_with_data = 0

        for commune in communes:
            code = commune.get("code") or commune.get("code_commune", "")
            if code not in socio_data:
                continue

            data = socio_data[code]
            pop = data.get("population") or commune.get("population", 0)
            if not pop:
                continue

            communes_with_data += 1
            total_pop += pop

            # Genre
            if data.get("genre"):
                total_hommes += data["genre"].get("hommes") or 0
                total_femmes += data["genre"].get("femmes") or 0

            # Tranches d'âge (pondérées)
            if data.get("tranches_age"):
                for age_group, pct in data["tranches_age"].items():
                    if pct and age_group in age_totals:
                        age_totals[age_group] += pop * pct / 100

            # Chômage
            if data.get("taux_chomage"):
                chomeurs_total += pop * data["taux_chomage"] / 100
                actifs_total += pop

            # Propriétaires
            if data.get("pct_proprietaires"):
                proprietaires_total += pop * data["pct_proprietaires"] / 100
                menages_total += pop

            # Revenus
            if data.get("revenu_median"):
                revenus_list.append((pop, data["revenu_median"]))

            if data.get("taux_pauvrete"):
                pauvrete_list.append((pop, data["taux_pauvrete"]))

            # CSP
            if data.get("csp"):
                for csp_type, value in data["csp"].items():
                    if value and csp_type in csp_totals:
                        csp_totals[csp_type] += value

        if communes_with_data == 0 or total_pop == 0:
            return None

        # Calculer les pourcentages agrégés
        age_pct = {}
        for age_group, total in age_totals.items():
            if total > 0:
                age_pct[age_group] = round(total / total_pop * 100, 1)

        # Revenu médian pondéré
        revenu_median = None
        if revenus_list:
            weighted_sum = sum(pop * rev for pop, rev in revenus_list)
            total_weight = sum(pop for pop, _ in revenus_list)
            if total_weight > 0:
                revenu_median = round(weighted_sum / total_weight, 0)

        # Taux de pauvreté pondéré
        taux_pauvrete = None
        if pauvrete_list:
            weighted_sum = sum(pop * tp for pop, tp in pauvrete_list)
            total_weight = sum(pop for pop, _ in pauvrete_list)
            if total_weight > 0:
                taux_pauvrete = round(weighted_sum / total_weight, 1)

        # CSP en pourcentages
        csp_total = sum(csp_totals.values())
        csp_pct = {}
        if csp_total > 0:
            for csp_type, total in csp_totals.items():
                csp_pct[csp_type] = round(total / csp_total * 100, 1)

        # Genre agrégé
        genre = None
        genre_total = total_hommes + total_femmes
        if genre_total > 0:
            genre = {
                "hommes": round(total_hommes),
                "femmes": round(total_femmes),
                "pct_hommes": round(total_hommes / genre_total * 100, 1),
                "pct_femmes": round(total_femmes / genre_total * 100, 1),
            }

        # Estimation taux de mobinautes basée sur profil démographique de la zone
        # Sources: ARCEP/Médiamétrie 2024: 87% des Français sont mobinautes
        # Taux par tranche d'âge (estimations ARCEP/Médiamétrie):
        # 15-29: 98%, 30-44: 96%, 45-59: 90%, 60-74: 78%, 75+: 45%, 0-14: 30%
        taux_mobinautes = None
        if age_pct:
            TAUX_MOBILE_PAR_AGE = {
                "0-14": 30.0, "15-29": 98.0, "30-44": 96.0,
                "45-59": 90.0, "60-74": 78.0, "75+": 45.0,
            }
            weighted_mobile = sum(
                age_pct.get(ag, 0) * TAUX_MOBILE_PAR_AGE.get(ag, 80) / 100
                for ag in TAUX_MOBILE_PAR_AGE
            )
            taux_mobinautes = round(weighted_mobile, 1)

        return {
            "communes_couvertes": communes_with_data,
            "genre": genre,
            "tranches_age": age_pct if age_pct else None,
            "taux_chomage": round(chomeurs_total / actifs_total * 100, 1) if actifs_total > 0 else None,
            "pct_proprietaires": round(proprietaires_total / menages_total * 100, 1) if menages_total > 0 else None,
            "revenu_median": revenu_median,
            "taux_pauvrete": taux_pauvrete,
            "taux_mobinautes": taux_mobinautes,
            "csp": csp_pct if csp_pct else None,
        }

    # =========================================================================
    # Données socio-démographiques INSEE
    # =========================================================================

    async def get_socio_demo_data(self, commune_codes: List[str] = None) -> Dict[str, Dict]:
        """
        Récupère les données socio-démographiques INSEE pour les communes.
        Retourne un dictionnaire indexé par code commune.

        Indicateurs clés extraits:
        - Population par tranches d'âge
        - Taux d'activité / chômage
        - CSP (cadres, employés, ouvriers, etc.)
        - Niveau de diplôme
        - Type de logement (propriétaires/locataires)
        - Revenus médians
        """
        data = await self.fetch_dataset("insee_socio_demo")

        if not data:
            logger.warning("Socio-demo data not available")
            return {}

        result = {}

        for row in data:
            try:
                # Code commune (CODGEO)
                code = row.get("CODGEO") or row.get("COM") or ""
                if not code:
                    continue

                if commune_codes and code not in commune_codes:
                    continue

                # Population totale
                pop_total = self._safe_float(row.get("P21_POP") or row.get("P20_POP") or row.get("P19_POP"))

                # Population par genre
                pop_hommes = self._safe_float(row.get("P21_POPH") or row.get("P20_POPH"))
                pop_femmes = self._safe_float(row.get("P21_POPF") or row.get("P20_POPF"))

                # Tranches d'âge (pourcentages)
                pop_0_14 = self._safe_float(row.get("P21_POP0014") or row.get("P20_POP0014"))
                pop_15_29 = self._safe_float(row.get("P21_POP1529") or row.get("P20_POP1529"))
                pop_30_44 = self._safe_float(row.get("P21_POP3044") or row.get("P20_POP3044"))
                pop_45_59 = self._safe_float(row.get("P21_POP4559") or row.get("P20_POP4559"))
                pop_60_74 = self._safe_float(row.get("P21_POP6074") or row.get("P20_POP6074"))
                pop_75_plus = self._safe_float(row.get("P21_POP75P") or row.get("P20_POP75P"))

                # CSP des 15-64 ans
                csp_cadres = self._safe_float(row.get("C21_POP15P_CS3") or row.get("C20_POP15P_CS3"))  # Cadres
                csp_prof_inter = self._safe_float(row.get("C21_POP15P_CS4") or row.get("C20_POP15P_CS4"))  # Prof. intermédiaires
                csp_employes = self._safe_float(row.get("C21_POP15P_CS5") or row.get("C20_POP15P_CS5"))  # Employés
                csp_ouvriers = self._safe_float(row.get("C21_POP15P_CS6") or row.get("C20_POP15P_CS6"))  # Ouvriers
                csp_retraites = self._safe_float(row.get("C21_POP15P_CS7") or row.get("C20_POP15P_CS7"))  # Retraités

                # Diplômes (15 ans et plus hors scolarisés)
                dipl_sans = self._safe_float(row.get("P21_NSCOL15P_DIPLMIN") or row.get("P20_NSCOL15P_DIPLMIN"))  # Sans diplôme
                dipl_bac = self._safe_float(row.get("P21_NSCOL15P_BAC") or row.get("P20_NSCOL15P_BAC"))  # Bac
                dipl_sup = self._safe_float(row.get("P21_NSCOL15P_SUP") or row.get("P20_NSCOL15P_SUP"))  # Supérieur

                # Activité
                actifs = self._safe_float(row.get("P21_ACT1564") or row.get("P20_ACT1564"))
                chomeurs = self._safe_float(row.get("P21_CHOM1564") or row.get("P20_CHOM1564"))

                # Logement
                menages = self._safe_float(row.get("P21_MEN") or row.get("P20_MEN"))
                proprietaires = self._safe_float(row.get("P21_RP_PROP") or row.get("P20_RP_PROP"))
                locataires = self._safe_float(row.get("P21_RP_LOC") or row.get("P20_RP_LOC"))

                # Revenus (si disponibles)
                revenu_median = self._safe_float(row.get("MED21") or row.get("MED20") or row.get("MED19"))
                taux_pauvrete = self._safe_float(row.get("TP60") or row.get("TP6021") or row.get("TP6020"))

                # Genre
                genre = None
                if pop_total and pop_total > 0 and pop_hommes is not None and pop_femmes is not None:
                    genre = {
                        "hommes": pop_hommes,
                        "femmes": pop_femmes,
                        "pct_hommes": round(pop_hommes / pop_total * 100, 1),
                        "pct_femmes": round(pop_femmes / pop_total * 100, 1),
                    }

                # Calculer pourcentages si on a les valeurs absolues
                pct_age = {}
                if pop_total and pop_total > 0:
                    if pop_0_14: pct_age["0-14"] = round(pop_0_14 / pop_total * 100, 1)
                    if pop_15_29: pct_age["15-29"] = round(pop_15_29 / pop_total * 100, 1)
                    if pop_30_44: pct_age["30-44"] = round(pop_30_44 / pop_total * 100, 1)
                    if pop_45_59: pct_age["45-59"] = round(pop_45_59 / pop_total * 100, 1)
                    if pop_60_74: pct_age["60-74"] = round(pop_60_74 / pop_total * 100, 1)
                    if pop_75_plus: pct_age["75+"] = round(pop_75_plus / pop_total * 100, 1)

                # Taux de chômage
                taux_chomage = None
                if actifs and actifs > 0 and chomeurs:
                    taux_chomage = round(chomeurs / actifs * 100, 1)

                # % propriétaires
                pct_proprietaires = None
                if menages and menages > 0 and proprietaires:
                    pct_proprietaires = round(proprietaires / menages * 100, 1)

                result[code] = {
                    "population": pop_total,
                    "genre": genre,
                    "tranches_age": pct_age if pct_age else None,
                    "taux_chomage": taux_chomage,
                    "pct_proprietaires": pct_proprietaires,
                    "revenu_median": revenu_median,
                    "taux_pauvrete": taux_pauvrete,
                    "csp": {
                        "cadres": csp_cadres,
                        "prof_intermediaires": csp_prof_inter,
                        "employes": csp_employes,
                        "ouvriers": csp_ouvriers,
                        "retraites": csp_retraites,
                    } if any([csp_cadres, csp_prof_inter, csp_employes, csp_ouvriers]) else None,
                }

            except Exception as e:
                logger.debug(f"Error parsing socio-demo row: {e}")
                continue

        return result

    def _safe_float(self, value) -> Optional[float]:
        """Convertit une valeur en float de manière sécurisée."""
        if value is None or value == "" or value == "s" or value == "nd":
            return None
        try:
            return float(str(value).replace(",", ".").replace(" ", ""))
        except (ValueError, TypeError):
            return None

    # =========================================================================
    # Bornes de recharge IRVE
    # =========================================================================

    async def get_irve_stations(
        self,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        radius_km: float = 20,
        department: Optional[str] = None,
    ) -> List[Dict]:
        """
        Récupère les bornes de recharge IRVE.
        Filtrage par rayon autour d'un point ou par département.
        """
        data = await self.fetch_dataset("irve_bornes")

        result = []
        for row in data:
            try:
                # Coordonnées
                lat_str = row.get("consolidated_latitude") or row.get("Ylatitude") or row.get("latitude")
                lng_str = row.get("consolidated_longitude") or row.get("Xlongitude") or row.get("longitude")

                if not lat_str or not lng_str:
                    continue

                station_lat = float(str(lat_str).replace(",", "."))
                station_lng = float(str(lng_str).replace(",", "."))

                # Filtre par département
                code_postal = row.get("consolidated_code_postal") or row.get("code_postal") or ""
                dep = code_postal[:2] if len(code_postal) >= 2 else ""
                if department and dep != department:
                    continue

                # Filtre par rayon
                if lat and lng:
                    dist = self._haversine(lat, lng, station_lat, station_lng)
                    if dist > radius_km:
                        continue
                else:
                    dist = None

                # Puissance
                puissance_str = row.get("puissance_nominale") or row.get("puissance_maximale") or "0"
                try:
                    puissance = float(str(puissance_str).replace(",", "."))
                except:
                    puissance = 0

                result.append({
                    "id": row.get("id_station_itinerance") or row.get("id_station_local"),
                    "nom": row.get("nom_station") or "Station IRVE",
                    "adresse": row.get("adresse_station") or row.get("consolidated_adresse") or "",
                    "commune": row.get("consolidated_commune") or row.get("nom_commune") or "",
                    "code_postal": code_postal,
                    "latitude": station_lat,
                    "longitude": station_lng,
                    "nb_points_charge": int(row.get("nbre_pdc") or 1),
                    "puissance_max_kw": puissance,
                    "operateur": row.get("nom_operateur") or row.get("nom_enseigne") or "",
                    "gratuit": row.get("gratuit") == "true" or row.get("gratuit") == "TRUE",
                    "accessibilite_pmr": row.get("accessibilite_pmr") == "true",
                    "distance_km": round(dist, 2) if dist else None,
                })

            except Exception as e:
                logger.debug(f"Error parsing IRVE row: {e}")
                continue

        # Tri par distance si disponible
        if lat and lng:
            result.sort(key=lambda x: x.get("distance_km") or 999)

        return result

    # =========================================================================
    # Données IDF Mobilités (Vélos, Covoiturage)
    # =========================================================================

    async def get_idf_bike_subsidies(self) -> Dict[str, Any]:
        """
        Récupère les stats de subventions vélo en Île-de-France.
        """
        data = await self.fetch_dataset("idf_subventions_velo")

        total_subventions = 0
        by_type = {}
        by_commune = {}

        for row in data:
            try:
                # Nombre de demandes
                nb_str = row.get("nombre_demandes") or row.get("nb_subventions") or "1"
                nb = int(float(str(nb_str).replace(",", ".")))
                total_subventions += nb

                # Type de vélo
                type_velo = row.get("type_velo") or row.get("type") or "Autre"
                by_type[type_velo] = by_type.get(type_velo, 0) + nb

                # Commune
                commune = row.get("commune") or row.get("libelle_commune") or ""
                if commune:
                    by_commune[commune] = by_commune.get(commune, 0) + nb

            except Exception:
                continue

        # Top communes
        top_communes = sorted(by_commune.items(), key=lambda x: x[1], reverse=True)[:20]

        return {
            "total_subventions": total_subventions,
            "by_type": by_type,
            "top_communes": [{"commune": c, "count": n} for c, n in top_communes],
        }

    async def get_idf_carpooling_stops(
        self,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        radius_km: float = 30,
    ) -> List[Dict]:
        """
        Récupère les arrêts de covoiturage IDF.
        """
        data = await self.fetch_dataset("idf_covoiturage")

        result = []
        for row in data:
            try:
                lat_str = row.get("Ylat") or row.get("latitude") or row.get("lat")
                lng_str = row.get("Xlong") or row.get("longitude") or row.get("lon")

                if not lat_str or not lng_str:
                    continue

                stop_lat = float(str(lat_str).replace(",", "."))
                stop_lng = float(str(lng_str).replace(",", "."))

                # Filtre par rayon
                if lat and lng:
                    dist = self._haversine(lat, lng, stop_lat, stop_lng)
                    if dist > radius_km:
                        continue
                else:
                    dist = None

                result.append({
                    "id": row.get("id_lieu") or row.get("id"),
                    "nom": row.get("nom_lieu") or row.get("nom") or "Arrêt covoiturage",
                    "commune": row.get("com_lieu") or row.get("commune") or "",
                    "latitude": stop_lat,
                    "longitude": stop_lng,
                    "nb_places": int(row.get("nbre_pl") or row.get("places") or 0),
                    "eclairage": row.get("lumiere") == "true" or row.get("eclairage") == "Oui",
                    "distance_km": round(dist, 2) if dist else None,
                })

            except Exception:
                continue

        if lat and lng:
            result.sort(key=lambda x: x.get("distance_km") or 999)

        return result

    async def get_idf_bike_parkings(self) -> List[Dict]:
        """
        Récupère la fréquentation des parkings vélos IDF.
        """
        data = await self.fetch_dataset("idf_parkings_velos")

        result = []
        for row in data:
            try:
                result.append({
                    "station": row.get("nom_gare") or row.get("station") or "",
                    "capacite": int(row.get("capacite") or row.get("nb_places") or 0),
                    "occupation": int(row.get("occupation") or row.get("nb_occupes") or 0),
                    "taux_occupation": float(row.get("taux_occupation") or 0),
                    "trimestre": row.get("trimestre") or "",
                })
            except Exception:
                continue

        return result

    # =========================================================================
    # GeoJSON boundaries
    # =========================================================================

    async def get_geojson_boundaries(
        self,
        boundary_type: str = "departements",
        code_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Récupère les contours géographiques (communes, départements, EPCI, académies).
        Cache local pour éviter les téléchargements répétés.
        """
        key = f"{boundary_type}_contours"
        if key not in GEOJSON_DATASETS:
            return {"type": "FeatureCollection", "features": []}

        cache_path = self.cache_dir / f"{key}.geojson"

        # Check cache
        if cache_path.exists():
            try:
                cache_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
                if datetime.now() - cache_time < timedelta(days=30):
                    with open(cache_path, "r", encoding="utf-8") as f:
                        geojson = json.load(f)
                    if code_filter:
                        geojson["features"] = [
                            f for f in geojson["features"]
                            if f.get("properties", {}).get("code", "").startswith(code_filter)
                        ]
                    return geojson
            except Exception as e:
                logger.error(f"GeoJSON cache read error: {e}")

        # Download
        url = GEOJSON_DATASETS[key]["url"]
        try:
            async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                geojson = response.json()

                # Save to cache
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(geojson, f, ensure_ascii=False)

                if code_filter:
                    geojson["features"] = [
                        f for f in geojson["features"]
                        if f.get("properties", {}).get("code", "").startswith(code_filter)
                    ]

                return geojson

        except Exception as e:
            logger.error(f"GeoJSON fetch error {url}: {e}")
            return {"type": "FeatureCollection", "features": []}

    # =========================================================================
    # Points d'intérêt (via API externe)
    # =========================================================================

    async def get_poi_nearby(
        self,
        lat: float,
        lng: float,
        radius_m: int = 1000,
        categories: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Récupère les POI à proximité via l'API Overpass (OpenStreetMap).
        Categories: restaurant, cafe, shop, hotel, pharmacy, bank, etc.
        """
        # Build Overpass query
        cat_filter = ""
        if categories:
            filters = []
            for cat in categories:
                if cat == "restaurant":
                    filters.append('node["amenity"="restaurant"]')
                elif cat == "cafe":
                    filters.append('node["amenity"="cafe"]')
                elif cat == "shop":
                    filters.append('node["shop"]')
                elif cat == "hotel":
                    filters.append('node["tourism"="hotel"]')
                elif cat == "pharmacy":
                    filters.append('node["amenity"="pharmacy"]')
                elif cat == "bank":
                    filters.append('node["amenity"="bank"]')
                elif cat == "supermarket":
                    filters.append('node["shop"="supermarket"]')
                elif cat == "bakery":
                    filters.append('node["shop"="bakery"]')
            cat_filter = "".join([f"{f}(around:{radius_m},{lat},{lng});" for f in filters])
        else:
            cat_filter = f'node["amenity"](around:{radius_m},{lat},{lng});node["shop"](around:{radius_m},{lat},{lng});'

        query = f"""
        [out:json][timeout:25];
        ({cat_filter});
        out body;
        """

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://overpass-api.de/api/interpreter",
                    data={"data": query},
                )
                response.raise_for_status()
                data = response.json()

                result = []
                for elem in data.get("elements", []):
                    tags = elem.get("tags", {})
                    result.append({
                        "id": elem.get("id"),
                        "name": tags.get("name", "Sans nom"),
                        "category": tags.get("amenity") or tags.get("shop") or tags.get("tourism") or "autre",
                        "latitude": elem.get("lat"),
                        "longitude": elem.get("lon"),
                        "address": tags.get("addr:street", ""),
                        "phone": tags.get("phone"),
                        "website": tags.get("website"),
                        "opening_hours": tags.get("opening_hours"),
                    })

                return result

        except Exception as e:
            logger.error(f"Overpass API error: {e}")
            return []

    # =========================================================================
    # Haversine distance calculation
    # =========================================================================

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in km."""
        from math import radians, sin, cos, sqrt, atan2
        R = 6371  # Earth radius in km

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

    # =========================================================================
    # Utilities
    # =========================================================================

    def get_cache_status(self) -> Dict[str, Any]:
        """Retourne le statut du cache."""
        status = {}
        for key in DATASETS:
            path = self._cache_path(key)
            if path.exists():
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                age = datetime.now() - mtime
                size = path.stat().st_size
                status[key] = {
                    "cached": True,
                    "age_hours": round(age.total_seconds() / 3600, 1),
                    "valid": age < timedelta(days=settings.DATAGOUV_CACHE_DAYS),
                    "size_kb": round(size / 1024, 1),
                }
            else:
                status[key] = {"cached": False}

        return status

    async def refresh_all(self):
        """Rafraîchit tous les datasets (skips heavy ones)."""
        logger.info("Refreshing all data.gouv.fr datasets...")
        for key in DATASETS:
            if key in HEAVY_DATASETS:
                logger.info(f"Skipping heavy dataset: {key}")
                continue
            await self.fetch_dataset(key, force_refresh=True)
        logger.info("All datasets refreshed")


# Singleton
datagouv_service = DataGouvService()

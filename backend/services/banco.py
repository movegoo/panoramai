"""
Service BANCO - Base Nationale des Commerces Ouverte.
Télécharge, cache et recherche les commerces par enseigne.
Source: https://www.data.gouv.fr/datasets/base-nationale-des-commerces-ouverte
"""
import csv
import io
import json
import logging
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

BANCO_CSV_URL = "https://www.data.gouv.fr/api/1/datasets/r/3d612ad7-f726-4fe5-a353-bdf76c5a44c2"

# Mapping noms concurrents -> termes de recherche BANCO
# Permet de gérer les variantes d'enseigne
BRAND_ALIASES = {
    # Grande distribution
    "carrefour": ["carrefour", "carrefour market", "carrefour city", "carrefour express", "carrefour contact"],
    "leclerc": ["leclerc", "e.leclerc", "e leclerc"],
    "lidl": ["lidl"],
    "auchan": ["auchan", "auchan supermarché", "auchan super"],
    "intermarché": ["intermarché", "intermarche"],
    "casino": ["casino", "géant casino", "petit casino", "casino supermarché"],
    "monoprix": ["monoprix", "monop'"],
    "franprix": ["franprix"],
    "picard": ["picard"],
    "biocoop": ["biocoop"],
    "système u": ["super u", "hyper u", "u express", "système u"],
    "cora": ["cora"],
    "match": ["match", "supermarché match"],
    # Bricolage / Maison
    "leroy merlin": ["leroy merlin"],
    "castorama": ["castorama"],
    "brico dépôt": ["brico dépôt", "brico depot", "bricodépôt", "bricodepot"],
    "bricomarché": ["bricomarché", "bricomarche"],
    "mr bricolage": ["mr bricolage", "mr.bricolage", "monsieur bricolage"],
    "point p": ["point p", "point.p"],
    "lapeyre": ["lapeyre"],
    "ikea": ["ikea"],
    "conforama": ["conforama"],
    "but": ["but"],
    "maisons du monde": ["maisons du monde"],
    # Sport
    "decathlon": ["decathlon"],
    "intersport": ["intersport"],
    "go sport": ["go sport"],
    # Mode
    "kiabi": ["kiabi"],
    "zara": ["zara"],
    "h&m": ["h&m", "h & m"],
    # Auto
    "norauto": ["norauto"],
    "feu vert": ["feu vert"],
}


class BancoService:
    """Service de téléchargement et recherche dans la base BANCO."""

    def __init__(self):
        self.cache_dir = settings.DATAGOUV_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._data: Optional[List[Dict]] = None

    @property
    def cache_path(self) -> Path:
        return self.cache_dir / "banco.json"

    def _is_cache_valid(self) -> bool:
        if not self.cache_path.exists():
            return False
        cache_time = datetime.fromtimestamp(self.cache_path.stat().st_mtime)
        return cache_time > datetime.now() - timedelta(days=30)

    async def download(self, force: bool = False) -> int:
        """Télécharge et cache la base BANCO. Retourne le nombre de commerces."""
        if not force and self._is_cache_valid():
            if self._data:
                return len(self._data)
            # Load from disk cache into memory
            return await self._load_from_cache()

        logger.info("Downloading BANCO database (38MB ZIP)...")

        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            response = await client.get(BANCO_CSV_URL)
            response.raise_for_status()

        # Extract CSV from ZIP
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            csv_files = [f for f in zf.namelist() if f.endswith('.csv')]
            if not csv_files:
                logger.error("No CSV file found in BANCO ZIP")
                return 0

            target = csv_files[0]
            logger.info(f"Extracting: {target}")
            raw = zf.read(target)

        # Decode
        content = None
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                content = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if not content:
            logger.error("Cannot decode BANCO CSV")
            return 0

        # Parse - detect delimiter
        first_line = content.split('\n')[0]
        delimiter = ',' if first_line.count(',') > first_line.count(';') else ';'

        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        records = []

        for row in reader:
            # Only keep entries with brand/enseigne
            brand = (row.get("brand") or "").strip()
            if not brand:
                continue

            lat = row.get("Y") or row.get("y") or row.get("latitude")
            lon = row.get("X") or row.get("x") or row.get("longitude")

            try:
                lat_f = float(lat) if lat else None
                lon_f = float(lon) if lon else None
            except (ValueError, TypeError):
                lat_f = None
                lon_f = None

            postal_code = ""
            com_insee = (row.get("com_insee") or "").strip()
            if len(com_insee) == 5:
                postal_code = com_insee  # Approximation INSEE -> CP

            records.append({
                "name": (row.get("name") or "").strip(),
                "brand": brand,
                "type": (row.get("type") or "").strip(),
                "address": (row.get("address") or "").strip(),
                "postal_code": postal_code,
                "city": (row.get("com_nom") or "").strip(),
                "com_insee": com_insee,
                "latitude": lat_f,
                "longitude": lon_f,
                "siret": (row.get("siret") or "").strip(),
                "phone": (row.get("phone") or "").strip(),
                "website": (row.get("website") or "").strip(),
                "opening_hours": (row.get("opening_hours") or "").strip(),
            })

        self._data = records

        # Save to file cache
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False)
            logger.info(f"BANCO cached: {len(records)} commerces with brand")
        except Exception as e:
            logger.error(f"BANCO cache write error: {e}")

        return len(records)

    async def _load_from_cache(self) -> int:
        """Load from file cache into memory."""
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            logger.info(f"BANCO loaded from cache: {len(self._data)} records")
            return len(self._data)
        except Exception as e:
            logger.error(f"BANCO cache read error: {e}")
            self._data = []
            return 0

    async def ensure_loaded(self):
        """S'assure que la base est chargée en mémoire."""
        if self._data is None:
            await self.download()

    def _get_search_terms(self, competitor_name: str) -> List[str]:
        """Retourne les termes de recherche pour un concurrent."""
        name_lower = competitor_name.lower().strip()

        # Check aliases first
        for key, aliases in BRAND_ALIASES.items():
            if name_lower in key or key in name_lower:
                return aliases

        # Default: just the name
        return [name_lower]

    async def search_stores(self, competitor_name: str) -> List[Dict]:
        """Recherche les magasins d'un concurrent par nom d'enseigne."""
        await self.ensure_loaded()

        if not self._data:
            return []

        search_terms = self._get_search_terms(competitor_name)
        results = []

        for record in self._data:
            brand_lower = record["brand"].lower()
            if any(term in brand_lower or brand_lower in term for term in search_terms):
                results.append(record)

        logger.info(f"BANCO search '{competitor_name}': {len(results)} stores found")
        return results

    async def search_and_store(self, competitor_id: int, competitor_name: str, db) -> int:
        """Cherche les magasins BANCO et les stocke en base."""
        from database import StoreLocation

        stores = await self.search_stores(competitor_name)

        if not stores:
            logger.info(f"No BANCO stores found for '{competitor_name}'")
            return 0

        # Delete old entries for this competitor
        db.query(StoreLocation).filter(
            StoreLocation.competitor_id == competitor_id,
            StoreLocation.source == "BANCO"
        ).delete()

        added = 0
        for store in stores:
            if not store.get("latitude") or not store.get("longitude"):
                continue

            dept = ""
            cp = store.get("postal_code", "")
            if len(cp) >= 2:
                dept = cp[:2]
                if dept == "20":
                    dept = "2A" if int(cp) < 20200 else "2B"

            loc = StoreLocation(
                competitor_id=competitor_id,
                name=store.get("name") or store.get("brand", ""),
                brand_name=store["brand"],
                category=store.get("type", ""),
                address=store.get("address", ""),
                postal_code=cp,
                city=store.get("city", ""),
                department=dept,
                latitude=store["latitude"],
                longitude=store["longitude"],
                siret=store.get("siret", ""),
                source="BANCO",
            )
            db.add(loc)
            added += 1

        db.commit()
        logger.info(f"BANCO: stored {added} locations for '{competitor_name}' (competitor_id={competitor_id})")

        # Free memory after storing to DB (data is now in SQLite)
        self._data = None

        return added

    async def get_all_brands(self) -> List[Dict]:
        """Retourne les enseignes uniques avec leur nombre de commerces."""
        await self.ensure_loaded()

        if not self._data:
            return []

        brand_counts: Dict[str, int] = {}
        for record in self._data:
            brand = record["brand"]
            brand_counts[brand] = brand_counts.get(brand, 0) + 1

        # Free memory after aggregation
        self._data = None

        return sorted(
            [{"brand": k, "count": v} for k, v in brand_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )


# Singleton
banco_service = BancoService()

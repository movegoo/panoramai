"""
Service BANCO - Base Nationale des Commerces Ouverte.
Télécharge sur disque, streame le CSV et importe en base par lots.
Mémoire peak: ~5MB (vs 56MB avant).
Source: https://www.data.gouv.fr/datasets/base-nationale-des-commerces-ouverte
"""
import csv
import io
import logging
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

BANCO_CSV_URL = "https://www.data.gouv.fr/api/1/datasets/r/3d612ad7-f726-4fe5-a353-bdf76c5a44c2"

# Mapping noms concurrents -> termes de recherche BANCO
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

BATCH_SIZE = 1000


class BancoService:
    """Service BANCO - streaming disk-based, no in-memory dataset."""

    def __init__(self):
        self.cache_dir = settings.DATAGOUV_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Legacy compat: _data is never used but some code references it
        self._data = None

    @property
    def _csv_path(self) -> Path:
        return self.cache_dir / "banco.csv"

    @property
    def _zip_path(self) -> Path:
        return self.cache_dir / "banco.zip"

    def _is_csv_fresh(self) -> bool:
        if not self._csv_path.exists():
            return False
        mtime = datetime.fromtimestamp(self._csv_path.stat().st_mtime)
        return mtime > datetime.now() - timedelta(days=30)

    async def _ensure_csv_on_disk(self, force: bool = False):
        """Download ZIP and extract CSV to disk. Streaming download, minimal memory."""
        if not force and self._is_csv_fresh():
            return

        logger.info("BANCO: downloading ZIP (38MB) to disk...")

        # Stream download to disk (8KB chunks, no full response in memory)
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            async with client.stream("GET", BANCO_CSV_URL) as response:
                response.raise_for_status()
                with open(self._zip_path, "wb") as f:
                    async for chunk in response.aiter_bytes(8192):
                        f.write(chunk)

        logger.info("BANCO: extracting CSV from ZIP...")

        # Extract CSV to disk (streaming copy)
        with zipfile.ZipFile(self._zip_path) as zf:
            csv_files = [f for f in zf.namelist() if f.endswith(".csv")]
            if not csv_files:
                self._zip_path.unlink(missing_ok=True)
                raise RuntimeError("No CSV found in BANCO ZIP")
            with zf.open(csv_files[0]) as src, open(self._csv_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

        # Free disk: delete ZIP
        self._zip_path.unlink(missing_ok=True)
        logger.info(f"BANCO: CSV extracted ({self._csv_path.stat().st_size // 1_000_000}MB)")

    def _detect_csv_params(self) -> tuple:
        """Detect encoding and delimiter of the cached CSV."""
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                with open(self._csv_path, "r", encoding=enc) as f:
                    first_line = f.readline()
                delim = "," if first_line.count(",") > first_line.count(";") else ";"
                return enc, delim
            except UnicodeDecodeError:
                continue
        return "latin-1", ";"

    def _get_search_terms(self, competitor_name: str) -> List[str]:
        """Retourne les termes de recherche pour un concurrent."""
        name_lower = competitor_name.lower().strip()
        for key, aliases in BRAND_ALIASES.items():
            if name_lower in key or key in name_lower:
                return aliases
        return [name_lower]

    def _parse_row(self, row: dict, competitor_id: int):
        """Parse a CSV row into a StoreLocation or None."""
        from database import StoreLocation

        lat = row.get("Y") or row.get("y") or row.get("latitude")
        lon = row.get("X") or row.get("x") or row.get("longitude")
        try:
            lat_f = float(lat) if lat else None
            lon_f = float(lon) if lon else None
        except (ValueError, TypeError):
            return None
        if not lat_f or not lon_f:
            return None

        cp = (row.get("com_insee") or "").strip()
        dept = ""
        if len(cp) >= 2:
            dept = cp[:2]
            if dept == "20":
                try:
                    dept = "2A" if int(cp) < 20200 else "2B"
                except ValueError:
                    pass

        return StoreLocation(
            competitor_id=competitor_id,
            name=(row.get("name") or row.get("brand", "")).strip()[:255],
            brand_name=(row.get("brand") or "").strip()[:255],
            category=(row.get("type") or "").strip()[:100],
            address=(row.get("address") or "").strip()[:500],
            postal_code=cp[:10],
            city=(row.get("com_nom") or "").strip()[:100],
            department=dept[:10],
            latitude=lat_f,
            longitude=lon_f,
            siret=(row.get("siret") or "").strip()[:20],
            source="BANCO",
        )

    async def search_and_store(self, competitor_id: int, competitor_name: str, db) -> int:
        """Stream CSV from disk, filter for one competitor, insert in batches.
        Memory: ~5MB peak."""
        from database import StoreLocation

        await self._ensure_csv_on_disk()

        search_terms = self._get_search_terms(competitor_name)

        # Delete old entries
        db.query(StoreLocation).filter(
            StoreLocation.competitor_id == competitor_id,
            StoreLocation.source == "BANCO",
        ).delete()

        enc, delim = self._detect_csv_params()
        added = 0
        batch = []

        with open(self._csv_path, "r", encoding=enc, errors="replace") as f:
            reader = csv.DictReader(f, delimiter=delim)
            for row in reader:
                brand = (row.get("brand") or "").strip().lower()
                if not brand:
                    continue
                if not any(term in brand or brand in term for term in search_terms):
                    continue

                loc = self._parse_row(row, competitor_id)
                if loc:
                    batch.append(loc)
                    added += 1

                if len(batch) >= BATCH_SIZE:
                    db.bulk_save_objects(batch)
                    db.flush()
                    batch = []

        if batch:
            db.bulk_save_objects(batch)
        db.commit()

        logger.info(f"BANCO: {added} stores for '{competitor_name}'")
        return added

    async def bulk_import(self, competitors: list, db) -> dict:
        """Import stores for ALL competitors in a single CSV pass.
        Downloads once, streams once, inserts by batch. Memory: ~5MB peak."""
        from database import StoreLocation
        from sqlalchemy import func

        if not competitors:
            return {}

        # Check which competitors already have BANCO data
        comp_ids = [c.id for c in competitors]
        existing = dict(
            db.query(StoreLocation.competitor_id, func.count(StoreLocation.id))
            .filter(StoreLocation.source == "BANCO", StoreLocation.competitor_id.in_(comp_ids))
            .group_by(StoreLocation.competitor_id)
            .all()
        )

        todo = {c.id: c.name for c in competitors if existing.get(c.id, 0) == 0}
        if not todo:
            logger.info("BANCO bulk_import: all competitors already have data")
            return {}

        await self._ensure_csv_on_disk()

        # Build search terms for all pending competitors
        comp_terms = {}
        for cid, cname in todo.items():
            comp_terms[cid] = self._get_search_terms(cname)

        enc, delim = self._detect_csv_params()
        counts = {cid: 0 for cid in comp_terms}
        batch = []

        with open(self._csv_path, "r", encoding=enc, errors="replace") as f:
            reader = csv.DictReader(f, delimiter=delim)
            for row in reader:
                brand = (row.get("brand") or "").strip().lower()
                if not brand:
                    continue

                # Check all competitors
                matched_cid = None
                for cid, terms in comp_terms.items():
                    if any(term in brand or brand in term for term in terms):
                        matched_cid = cid
                        break
                if not matched_cid:
                    continue

                loc = self._parse_row(row, matched_cid)
                if loc:
                    batch.append(loc)
                    counts[matched_cid] += 1

                if len(batch) >= BATCH_SIZE:
                    db.bulk_save_objects(batch)
                    db.flush()
                    batch = []

        if batch:
            db.bulk_save_objects(batch)
        db.commit()

        for cid, cnt in counts.items():
            if cnt > 0:
                logger.info(f"BANCO: {cnt} stores for '{todo[cid]}'")

        return counts

    async def download(self, force: bool = False) -> int:
        """Download BANCO CSV to disk. Returns estimated record count."""
        await self._ensure_csv_on_disk(force=force)
        # Count lines without loading into memory
        count = 0
        enc, _ = self._detect_csv_params()
        with open(self._csv_path, "r", encoding=enc, errors="replace") as f:
            for _ in f:
                count += 1
        return count - 1  # minus header

    async def get_all_brands(self) -> List[Dict]:
        """Stream CSV and aggregate brand counts. Memory: ~2MB."""
        await self._ensure_csv_on_disk()

        enc, delim = self._detect_csv_params()
        brand_counts: Dict[str, int] = {}

        with open(self._csv_path, "r", encoding=enc, errors="replace") as f:
            reader = csv.DictReader(f, delimiter=delim)
            for row in reader:
                brand = (row.get("brand") or "").strip()
                if brand:
                    brand_counts[brand] = brand_counts.get(brand, 0) + 1

        return sorted(
            [{"brand": k, "count": v} for k, v in brand_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )


# Singleton
banco_service = BancoService()

"""Tests for services/geodata.py — Geographic data service."""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from services.geodata import (
    haversine_distance,
    get_bounding_box,
    get_communes_by_department,
    find_nearest_commune,
    GeoDataService,
    COMMUNES_REFERENCE,
)


# ─── Haversine distance ──────────────────────────────────────────

class TestHaversineDistance:
    def test_same_point(self):
        d = haversine_distance(48.8566, 2.3522, 48.8566, 2.3522)
        assert d == pytest.approx(0.0, abs=0.001)

    def test_paris_lyon(self):
        # Paris to Lyon ≈ 392 km
        d = haversine_distance(48.8566, 2.3522, 45.7640, 4.8357)
        assert 380 < d < 410

    def test_paris_marseille(self):
        # Paris to Marseille ≈ 660 km
        d = haversine_distance(48.8566, 2.3522, 43.2965, 5.3698)
        assert 650 < d < 680

    def test_short_distance(self):
        # ~1.5km in Paris
        d = haversine_distance(48.8566, 2.3522, 48.8600, 2.3700)
        assert 0.5 < d < 3.0


# ─── Bounding box ────────────────────────────────────────────────

class TestBoundingBox:
    def test_paris_10km(self):
        bbox = get_bounding_box(48.8566, 2.3522, 10)
        assert bbox["min_lat"] < 48.8566 < bbox["max_lat"]
        assert bbox["min_lon"] < 2.3522 < bbox["max_lon"]
        # Approx check: ~0.09° lat per 10km
        lat_delta = bbox["max_lat"] - bbox["min_lat"]
        assert 0.15 < lat_delta < 0.25

    def test_equator(self):
        bbox = get_bounding_box(0, 0, 100)
        assert bbox["min_lat"] == pytest.approx(-100 / 111, rel=0.01)


# ─── Communes reference data ─────────────────────────────────────

class TestCommunesReference:
    def test_has_paris(self):
        paris = [c for c in COMMUNES_REFERENCE if c["nom"] == "Paris"]
        assert len(paris) == 1
        assert paris[0]["code"] == "75056"

    def test_get_communes_by_department(self):
        lyon_dept = get_communes_by_department("69")
        assert any(c["nom"] == "Lyon" for c in lyon_dept)

    def test_empty_department(self):
        assert get_communes_by_department("00") == []

    def test_find_nearest_commune_paris(self):
        result = find_nearest_commune(48.86, 2.35)
        assert result["nom"] == "Paris"
        assert result["distance_km"] < 1.0

    def test_find_nearest_commune_lyon(self):
        result = find_nearest_commune(45.76, 4.84)
        assert result["nom"] == "Lyon"
        assert result["distance_km"] < 1.0


# ─── GeoDataService ──────────────────────────────────────────────

class TestGeoDataService:
    @pytest.mark.asyncio
    async def test_fetch_csv_success(self):
        svc = GeoDataService()
        csv_content = b"col1;col2\nval1;val2\nval3;val4"

        mock_response = MagicMock()
        mock_response.content = csv_content
        mock_response.raise_for_status = MagicMock()

        with patch("services.geodata.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await svc.fetch_csv("http://example.com/data.csv")

        assert len(result) == 2
        assert result[0]["col1"] == "val1"

    @pytest.mark.asyncio
    async def test_fetch_csv_error(self):
        svc = GeoDataService()
        with patch("services.geodata.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
            mock_client_cls.return_value = mock_client

            result = await svc.fetch_csv("http://example.com/data.csv")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_loyers_cached(self):
        svc = GeoDataService()
        svc.cache["loyers"] = [{"code_commune": "75056", "loyer_moyen_m2": 25.0}]
        result = await svc.get_loyers_data()
        assert len(result) == 1
        assert result[0]["loyer_moyen_m2"] == 25.0

    @pytest.mark.asyncio
    async def test_get_population_cached(self):
        svc = GeoDataService()
        svc.cache["population"] = [{"code_commune": "75056", "population": 2148000}]
        result = await svc.get_population_data()
        assert result[0]["population"] == 2148000

    @pytest.mark.asyncio
    async def test_get_equipements_cached(self):
        svc = GeoDataService()
        svc.cache["equipements_75000"] = [{"type_equipement": "A101"}]
        result = await svc.get_equipements_data("75000")
        assert len(result) == 1

    def test_analyze_zone_with_data(self):
        svc = GeoDataService()
        communes = [
            {"latitude": 48.86, "longitude": 2.35, "population": 2148000, "loyer_moyen_m2": 25.0},
            {"latitude": 48.87, "longitude": 2.36, "population": 50000, "loyer_moyen_m2": 22.0},
            {"latitude": 45.76, "longitude": 4.84, "population": 522000, "loyer_moyen_m2": 12.0},  # Lyon, far
        ]
        result = svc.analyze_zone(48.8566, 2.3522, 5, communes)
        assert result["nb_communes"] == 2
        assert result["population_totale"] == 2148000 + 50000
        assert result["loyer_moyen_m2"] is not None

    def test_analyze_zone_empty(self):
        svc = GeoDataService()
        result = svc.analyze_zone(48.8566, 2.3522, 1, [])
        assert result["nb_communes"] == 0
        assert result["population_totale"] == 0

    def test_analyze_zone_missing_coords(self):
        svc = GeoDataService()
        communes = [{"population": 1000}]  # no lat/lon
        result = svc.analyze_zone(48.86, 2.35, 10, communes)
        assert result["nb_communes"] == 0

"""Tests for GMB scoring logic and extended field parsing."""
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from services.gmb_service import compute_gmb_score, GMBService


class TestComputeGmbScore:
    """Test the composite GMB score calculation (0-100)."""

    def test_perfect_score(self):
        """Store with excellent rating, many reviews, full profile, and open."""
        score = compute_gmb_score(
            rating=4.7,
            reviews_count=300,
            phone="+33 1 23 45 67 89",
            website="https://example.com",
            hours='["Lundi: 9h-19h"]',
            thumbnail="https://img.com/photo.jpg",
            gtype="supermarket",
            open_state="Ouvert",
        )
        # 30 (rating 4.5+) + 25 (200+ reviews) + 25 (5 fields) + 20 (open) = 100
        assert score == 100

    def test_minimal_score(self):
        """Store with bad rating, few reviews, no profile, no open state."""
        score = compute_gmb_score(
            rating=2.5,
            reviews_count=3,
        )
        # 5 (rating <3.5) + 2 (<10 reviews) + 0 (no fields) + 10 (no state) = 17
        assert score == 17

    def test_no_data_at_all(self):
        """Store with zero info."""
        score = compute_gmb_score()
        # 0 + 0 + 0 + 10 (no state = neutral) = 10
        assert score == 10

    def test_rating_tiers(self):
        """Verify each rating tier gives the right points."""
        assert compute_gmb_score(rating=4.8) >= 30  # includes neutral status
        assert compute_gmb_score(rating=4.2) >= 22
        assert compute_gmb_score(rating=3.7) >= 15
        assert compute_gmb_score(rating=3.0) >= 5

    def test_reviews_tiers(self):
        """Verify review count tiers."""
        # 200+ reviews = 25 pts
        s200 = compute_gmb_score(reviews_count=250)
        # 100-199 = 18 pts
        s100 = compute_gmb_score(reviews_count=150)
        # 50-99 = 12 pts
        s50 = compute_gmb_score(reviews_count=75)
        # 10-49 = 6 pts
        s10 = compute_gmb_score(reviews_count=25)
        # <10 = 2 pts
        s5 = compute_gmb_score(reviews_count=5)

        assert s200 > s100 > s50 > s10 > s5

    def test_completeness_fields(self):
        """Each profile field adds 5 pts."""
        base = compute_gmb_score()
        with_phone = compute_gmb_score(phone="+33 1 00 00 00 00")
        assert with_phone == base + 5

        with_two = compute_gmb_score(phone="+33 1 00 00 00 00", website="https://x.com")
        assert with_two == base + 10

    def test_open_state_values(self):
        """Open = 20pts, temporarily closed = 5pts, other = 10pts."""
        s_open = compute_gmb_score(open_state="Ouvert")
        s_temp = compute_gmb_score(open_state="Fermé temporairement")
        s_none = compute_gmb_score(open_state=None)

        assert s_open > s_none > s_temp

    def test_open_state_english(self):
        """English open state values also work."""
        s_open = compute_gmb_score(open_state="Open now")
        s_closed = compute_gmb_score(open_state="Temporarily closed")
        assert s_open > s_closed

    def test_score_capped_at_100(self):
        """Score should never exceed 100."""
        score = compute_gmb_score(
            rating=5.0,
            reviews_count=10000,
            phone="x",
            website="x",
            hours="x",
            thumbnail="x",
            gtype="x",
            open_state="Ouvert",
        )
        assert score <= 100


class TestSearchAPIExtendedFields:
    """Test that SearchAPI response parsing extracts extended fields."""

    def setup_method(self):
        self.service = GMBService()

    @pytest.mark.asyncio
    async def test_searchapi_extracts_extended_fields(self):
        """Verify phone, website, type, thumbnail, hours, price are extracted."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "local_results": [
                {
                    "title": "Carrefour Marseille",
                    "rating": 3.9,
                    "reviews": 420,
                    "place_id": "ChIJtest",
                    "address": "123 Rue de Test",
                    "phone": "+33 4 91 00 00 00",
                    "website": "https://carrefour.fr",
                    "type": "Supermarché",
                    "thumbnail": "https://img.example.com/photo.jpg",
                    "open_state": "Ouvert",
                    "operating_hours": {"monday": "8:00-21:00", "tuesday": "8:00-21:00"},
                    "price": "$$",
                    "gps_coordinates": {"latitude": 43.30, "longitude": 5.37},
                }
            ]
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.gmb_service.httpx.AsyncClient", return_value=mock_client):
            with patch.object(type(self.service), "searchapi_key",
                              new_callable=lambda: property(lambda self: "test_key")):
                result = await self.service._searchapi_lookup(
                    "Carrefour", "Carrefour", "Marseille", 43.30, 5.37
                )

        assert result["success"] is True
        assert result["phone"] == "+33 4 91 00 00 00"
        assert result["website"] == "https://carrefour.fr"
        assert result["type"] == "Supermarché"
        assert result["thumbnail"] == "https://img.example.com/photo.jpg"
        assert result["open_state"] == "Ouvert"
        assert result["price"] == "$$"
        # Hours should be JSON string
        hours = json.loads(result["hours"])
        assert hours["monday"] == "8:00-21:00"

    @pytest.mark.asyncio
    async def test_searchapi_missing_extended_fields(self):
        """Extended fields are None when not in response."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "local_results": [
                {
                    "title": "Lidl Test",
                    "rating": 4.0,
                    "reviews": 50,
                    "place_id": "ChIJmin",
                    "gps_coordinates": {"latitude": 48.85, "longitude": 2.35},
                }
            ]
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.gmb_service.httpx.AsyncClient", return_value=mock_client):
            with patch.object(type(self.service), "searchapi_key",
                              new_callable=lambda: property(lambda self: "test_key")):
                result = await self.service._searchapi_lookup(
                    "Lidl", "Lidl", "Paris", 48.85, 2.35
                )

        assert result["success"] is True
        assert result["phone"] is None
        assert result["website"] is None
        assert result["hours"] is None
        assert result["price"] is None


class TestGooglePlacesExtendedFields:
    """Test Google Places API extended field parsing."""

    def setup_method(self):
        self.service = GMBService()

    @pytest.mark.asyncio
    async def test_google_places_extracts_extended_fields(self):
        """Verify extended fields from Google Places response."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "candidates": [
                {
                    "name": "Leroy Merlin Lyon",
                    "rating": 4.3,
                    "user_ratings_total": 810,
                    "place_id": "ChIJgp",
                    "formatted_address": "45 Avenue Test, Lyon",
                    "formatted_phone_number": "+33 4 72 00 00 00",
                    "website": "https://leroymerlin.fr",
                    "types": ["home_goods_store", "store"],
                    "business_status": "OPERATIONAL",
                    "opening_hours": {
                        "weekday_text": ["Lundi: 07:00–20:00", "Mardi: 07:00–20:00"],
                    },
                    "price_level": 2,
                    "photos": [{"photo_reference": "abc123"}],
                }
            ]
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.gmb_service.httpx.AsyncClient", return_value=mock_client):
            with patch.object(type(self.service), "google_places_key",
                              new_callable=lambda: property(lambda self: "gp_key")):
                result = await self.service._google_places_lookup(
                    "Leroy Merlin", "Leroy Merlin", "Lyon", 45.75, 4.85
                )

        assert result["success"] is True
        assert result["phone"] == "+33 4 72 00 00 00"
        assert result["website"] == "https://leroymerlin.fr"
        assert result["type"] == "home_goods_store"
        assert result["open_state"] == "Ouvert"
        assert result["price"] == "$$"
        assert result["thumbnail"] is not None
        assert "abc123" in result["thumbnail"]
        # Hours
        hours = json.loads(result["hours"])
        assert "Lundi: 07:00–20:00" in hours

    @pytest.mark.asyncio
    async def test_google_places_temporarily_closed(self):
        """Business status TEMPORARILY_CLOSED maps correctly."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "candidates": [
                {
                    "name": "Test Store",
                    "rating": 3.5,
                    "user_ratings_total": 10,
                    "place_id": "ChIJclosed",
                    "formatted_address": "1 Rue Test",
                    "business_status": "TEMPORARILY_CLOSED",
                }
            ]
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.gmb_service.httpx.AsyncClient", return_value=mock_client):
            with patch.object(type(self.service), "google_places_key",
                              new_callable=lambda: property(lambda self: "gp_key")):
                result = await self.service._google_places_lookup("Test", "Test", "City")

        assert result["open_state"] == "Fermé temporairement"

"""Tests for competitors API endpoints."""
from database import Competitor, Advertiser, UserAdvertiser, AdvertiserCompetitor


class TestListCompetitors:
    def test_authenticated(self, client, adv_headers, test_competitor):
        response = client.get("/api/competitors/", headers=adv_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "Carrefour"

    def test_unauthenticated(self, client):
        response = client.get("/api/competitors/")
        assert response.status_code == 401


class TestCreateCompetitor:
    def test_success(self, client, adv_headers):
        response = client.post(
            "/api/competitors/",
            json={"name": "Lidl", "website": "https://lidl.fr"},
            headers=adv_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Lidl"


class TestGetCompetitor:
    def test_found(self, client, adv_headers, test_competitor):
        response = client.get(
            f"/api/competitors/{test_competitor.id}", headers=adv_headers
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Carrefour"

    def test_not_found(self, client, auth_headers):
        response = client.get("/api/competitors/9999", headers=auth_headers)
        assert response.status_code == 404

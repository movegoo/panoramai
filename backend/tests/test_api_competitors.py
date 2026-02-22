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


    def test_create_with_snapchat(self, client, adv_headers):
        response = client.post(
            "/api/competitors/",
            json={
                "name": "Auchan",
                "website": "https://auchan.fr",
                "snapchat_entity_name": "Auchan France",
            },
            headers=adv_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Auchan"


class TestSnapchatFieldRoundTrip:
    def test_create_and_read_snapchat(self, client, adv_headers):
        # Create competitor with snapchat_entity_name
        create_resp = client.post(
            "/api/competitors/",
            json={
                "name": "Snap Test Corp",
                "snapchat_entity_name": "SnapTestEntity",
            },
            headers=adv_headers,
        )
        assert create_resp.status_code == 200
        comp_id = create_resp.json()["id"]

        # Read it back via detail endpoint
        detail_resp = client.get(f"/api/competitors/{comp_id}", headers=adv_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["snapchat_entity_name"] == "SnapTestEntity"

    def test_update_snapchat(self, client, adv_headers, test_competitor):
        # Update existing competitor with snapchat_entity_name
        update_resp = client.put(
            f"/api/competitors/{test_competitor.id}",
            json={"snapchat_entity_name": "Carrefour Snap"},
            headers=adv_headers,
        )
        assert update_resp.status_code == 200
        assert "snapchat_entity_name" in update_resp.json().get("updated_fields", [])


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

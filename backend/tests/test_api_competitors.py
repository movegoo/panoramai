"""Tests for competitors API endpoints."""
from database import Competitor, Advertiser


class TestListCompetitors:
    def test_authenticated(self, client, auth_headers, test_user, db):
        user, _ = test_user
        # Create an advertiser for the user
        adv = Advertiser(user_id=user.id, company_name="Test Brand", sector="supermarche", is_active=True)
        db.add(adv)
        db.commit()
        db.refresh(adv)

        # Create a competitor
        comp = Competitor(
            user_id=user.id, advertiser_id=adv.id,
            name="Carrefour", website="https://carrefour.fr", is_active=True,
        )
        db.add(comp)
        db.commit()

        response = client.get("/api/competitors/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "Carrefour"

    def test_unauthenticated(self, client):
        response = client.get("/api/competitors/")
        assert response.status_code == 401


class TestCreateCompetitor:
    def test_success(self, client, auth_headers, test_user, db):
        user, _ = test_user
        adv = Advertiser(user_id=user.id, company_name="Test Brand", sector="supermarche", is_active=True)
        db.add(adv)
        db.commit()
        db.refresh(adv)

        response = client.post(
            "/api/competitors/",
            json={"name": "Lidl", "website": "https://lidl.fr"},
            headers={**auth_headers, "X-Advertiser-Id": str(adv.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Lidl"


class TestGetCompetitor:
    def test_found(self, client, auth_headers, test_user, db):
        user, _ = test_user
        adv = Advertiser(user_id=user.id, company_name="Test Brand", sector="supermarche", is_active=True)
        db.add(adv)
        db.commit()
        db.refresh(adv)

        comp = Competitor(
            user_id=user.id, advertiser_id=adv.id,
            name="Leclerc", website="https://leclerc.fr", is_active=True,
        )
        db.add(comp)
        db.commit()
        db.refresh(comp)

        response = client.get(f"/api/competitors/{comp.id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["name"] == "Leclerc"

    def test_not_found(self, client, auth_headers):
        response = client.get("/api/competitors/9999", headers=auth_headers)
        assert response.status_code == 404

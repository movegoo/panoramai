"""Tests for auth API endpoints."""
from database import Advertiser, UserAdvertiser


class TestRegister:
    def test_success(self, client):
        response = client.post("/api/auth/register", json={
            "email": "new@example.com",
            "password": "password123",
            "name": "New User",
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "new@example.com"
        assert data["user"]["name"] == "New User"

    def test_duplicate_email(self, client, test_user):
        response = client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "password123",
        })
        assert response.status_code == 400
        assert "déjà utilisé" in response.json()["detail"]

    def test_short_password(self, client):
        response = client.post("/api/auth/register", json={
            "email": "short@example.com",
            "password": "12345",
        })
        assert response.status_code == 400
        assert "6 caractères" in response.json()["detail"]


class TestLogin:
    def test_success(self, client, test_user):
        response = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "password123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "test@example.com"

    def test_wrong_password(self, client, test_user):
        response = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword",
        })
        assert response.status_code == 401

    def test_unknown_email(self, client):
        response = client.post("/api/auth/login", json={
            "email": "unknown@example.com",
            "password": "password123",
        })
        assert response.status_code == 401


class TestMe:
    def test_with_token(self, client, auth_headers, test_user, db):
        user, _ = test_user
        adv = Advertiser(company_name="My Brand", sector="supermarche", is_active=True)
        db.add(adv)
        db.commit()
        db.refresh(adv)
        link = UserAdvertiser(user_id=user.id, advertiser_id=adv.id, role="owner")
        db.add(link)
        db.commit()

        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "advertisers" in data
        assert len(data["advertisers"]) >= 1
        assert data["advertisers"][0]["company_name"] == "My Brand"

    def test_without_token(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

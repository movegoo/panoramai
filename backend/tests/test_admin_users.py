"""Tests for admin user management endpoints."""
from database import User
from core.auth import hash_password


class TestUpdateUser:
    def test_admin_can_update_name(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        other = User(email="target@example.com", name="Old Name", password_hash=hash_password("pass123"))
        db.add(other)
        db.commit()
        db.refresh(other)

        resp = client.put(f"/api/admin/users/{other.id}", headers=auth_headers,
                          json={"name": "New Name"})
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data["updated_fields"]
        assert data["user"]["name"] == "New Name"

    def test_admin_can_update_email(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        other = User(email="old@example.com", name="User", password_hash=hash_password("pass123"))
        db.add(other)
        db.commit()
        db.refresh(other)

        resp = client.put(f"/api/admin/users/{other.id}", headers=auth_headers,
                          json={"email": "new@example.com"})
        assert resp.status_code == 200
        assert resp.json()["user"]["email"] == "new@example.com"

    def test_duplicate_email_rejected(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        other = User(email="taken@example.com", name="X", password_hash=hash_password("pass123"))
        db.add(other)
        db.commit()

        # Try to set test_user's email to taken one
        resp = client.put(f"/api/admin/users/{user.id}", headers=auth_headers,
                          json={"email": "taken@example.com"})
        assert resp.status_code == 400
        assert "déjà utilisé" in resp.json()["detail"]

    def test_toggle_is_active(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        other = User(email="active@example.com", name="A", password_hash=hash_password("p"), is_active=True)
        db.add(other)
        db.commit()
        db.refresh(other)

        resp = client.put(f"/api/admin/users/{other.id}", headers=auth_headers,
                          json={"is_active": False})
        assert resp.status_code == 200
        assert resp.json()["user"]["is_active"] is False

    def test_toggle_is_admin(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        other = User(email="user2@example.com", name="U", password_hash=hash_password("p"))
        db.add(other)
        db.commit()
        db.refresh(other)

        resp = client.put(f"/api/admin/users/{other.id}", headers=auth_headers,
                          json={"is_admin": True})
        assert resp.status_code == 200
        assert resp.json()["user"]["is_admin"] is True

    def test_cannot_deactivate_self(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        db.commit()

        resp = client.put(f"/api/admin/users/{user.id}", headers=auth_headers,
                          json={"is_active": False})
        assert resp.status_code == 400
        assert "propre compte" in resp.json()["detail"]

    def test_cannot_remove_own_admin(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        db.commit()

        resp = client.put(f"/api/admin/users/{user.id}", headers=auth_headers,
                          json={"is_admin": False})
        assert resp.status_code == 400
        assert "propre" in resp.json()["detail"]

    def test_reset_password(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        other = User(email="pw@example.com", name="PW", password_hash=hash_password("old"))
        db.add(other)
        db.commit()
        db.refresh(other)

        resp = client.put(f"/api/admin/users/{other.id}", headers=auth_headers,
                          json={"password": "newpass123"})
        assert resp.status_code == 200
        assert "password" in resp.json()["updated_fields"]

    def test_short_password_rejected(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        other = User(email="short@example.com", name="S", password_hash=hash_password("old"))
        db.add(other)
        db.commit()
        db.refresh(other)

        resp = client.put(f"/api/admin/users/{other.id}", headers=auth_headers,
                          json={"password": "ab"})
        assert resp.status_code == 400
        assert "6 caractères" in resp.json()["detail"]

    def test_user_not_found(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        db.commit()

        resp = client.put("/api/admin/users/99999", headers=auth_headers,
                          json={"name": "X"})
        assert resp.status_code == 404

    def test_non_admin_forbidden(self, client, auth_headers):
        resp = client.put("/api/admin/users/1", headers=auth_headers,
                          json={"name": "X"})
        assert resp.status_code == 403


class TestDeleteUser:
    def test_admin_can_delete_user(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        other = User(email="deleteme@example.com", name="D", password_hash=hash_password("p"))
        db.add(other)
        db.commit()
        db.refresh(other)

        resp = client.delete(f"/api/admin/users/{other.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert "supprimé" in resp.json()["message"]

        # Verify user is gone
        assert db.query(User).filter(User.id == other.id).first() is None

    def test_cannot_delete_self(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        db.commit()

        resp = client.delete(f"/api/admin/users/{user.id}", headers=auth_headers)
        assert resp.status_code == 400
        assert "propre compte" in resp.json()["detail"]

    def test_user_not_found(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        db.commit()

        resp = client.delete("/api/admin/users/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_non_admin_forbidden(self, client, auth_headers):
        resp = client.delete("/api/admin/users/1", headers=auth_headers)
        assert resp.status_code == 403


class TestListUsers:
    def test_admin_can_list_users(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        db.commit()

        resp = client.get("/api/admin/users", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(u["email"] == "test@example.com" for u in data)
        # Check all expected fields are present
        u0 = data[0]
        for field in ["id", "email", "name", "is_active", "is_admin", "has_brand", "brand_name", "competitors_count"]:
            assert field in u0

    def test_non_admin_forbidden(self, client, auth_headers):
        resp = client.get("/api/admin/users", headers=auth_headers)
        assert resp.status_code == 403

"""Tests for feature access control system."""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from core.features import resolve_features, has_feature, FEATURE_REGISTRY, PAGES, get_registry_grouped
from database import UserAdvertiser, User, Advertiser
from core.auth import hash_password, create_access_token


class TestResolveFeatures:
    def test_null_returns_all_true(self):
        result = resolve_features(None)
        assert all(v is True for v in result.values())
        assert len(result) == len(FEATURE_REGISTRY)

    def test_empty_dict_returns_all_true(self):
        result = resolve_features({})
        assert all(v is True for v in result.values())

    def test_explicit_false_disables_feature(self):
        result = resolve_features({"seo": False})
        assert result["seo"] is False

    def test_page_false_cascades_to_blocks(self):
        result = resolve_features({"seo": False})
        assert result["seo"] is False
        assert result["seo.serp_rankings"] is False
        assert result["seo.sov_chart"] is False
        assert result["seo.missing_keywords"] is False
        # Other pages unaffected
        assert result["geo"] is True

    def test_block_false_doesnt_affect_page(self):
        result = resolve_features({"seo.sov_chart": False})
        assert result["seo"] is True
        assert result["seo.sov_chart"] is False
        assert result["seo.serp_rankings"] is True

    def test_unknown_keys_ignored(self):
        result = resolve_features({"nonexistent_page": False, "seo": True})
        assert result["seo"] is True
        assert "nonexistent_page" not in result


class TestHasFeature:
    def test_null_features(self):
        assert has_feature(None, "seo") is True
        assert has_feature(None, "seo.serp_rankings") is True

    def test_enabled(self):
        assert has_feature({"seo": True}, "seo") is True

    def test_disabled(self):
        assert has_feature({"seo": False}, "seo") is False

    def test_page_cascade_on_block(self):
        assert has_feature({"seo": False}, "seo.serp_rankings") is False

    def test_block_disabled_page_enabled(self):
        assert has_feature({"seo.sov_chart": False}, "seo") is True
        assert has_feature({"seo.sov_chart": False}, "seo.sov_chart") is False


class TestRegistryGrouped:
    def test_returns_all_pages(self):
        grouped = get_registry_grouped()
        for page in PAGES:
            assert page in grouped
            assert "label" in grouped[page]
            assert "blocks" in grouped[page]

    def test_blocks_have_labels(self):
        grouped = get_registry_grouped()
        for page, data in grouped.items():
            for block_key, block_label in data["blocks"].items():
                assert block_key.startswith(f"{page}.")
                assert isinstance(block_label, str)


class TestMeReturnsFeatures:
    def test_me_returns_features(self, client, db, test_user):
        user, token = test_user
        adv = Advertiser(company_name="Brand", sector="supermarche", is_active=True)
        db.add(adv)
        db.commit()
        db.refresh(adv)
        link = UserAdvertiser(user_id=user.id, advertiser_id=adv.id, role="owner")
        db.add(link)
        db.commit()

        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        # Features are on the user level, not per-advertiser
        assert "features" in data
        features = data["features"]
        assert isinstance(features, dict)
        assert features.get("seo") is True

    def test_me_null_features_returns_all_true(self, client, db, test_user):
        user, token = test_user
        adv = Advertiser(company_name="Brand2", sector="supermarche", is_active=True)
        db.add(adv)
        db.commit()
        db.refresh(adv)
        link = UserAdvertiser(user_id=user.id, advertiser_id=adv.id, role="owner")
        db.add(link)
        db.commit()

        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        data = response.json()
        features = data["features"]
        assert all(v is True for v in features.values())

    def test_me_with_restricted_features(self, client, db, test_user):
        user, token = test_user
        user.features = {"seo": False, "signals": False}
        db.commit()
        adv = Advertiser(company_name="Brand3", sector="supermarche", is_active=True)
        db.add(adv)
        db.commit()
        db.refresh(adv)
        link = UserAdvertiser(user_id=user.id, advertiser_id=adv.id, role="owner")
        db.add(link)
        db.commit()

        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        data = response.json()
        assert data["features"]["seo"] is False
        assert data["features"]["seo.serp_rankings"] is False  # cascade
        assert data["features"]["signals"] is False
        assert data["features"]["overview"] is True  # other pages unaffected


class TestAdminFeaturesEndpoints:
    def _make_admin(self, db):
        admin = User(
            email="admin@test.com",
            name="Admin",
            password_hash=hash_password("password123"),
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        token = create_access_token(admin.id)
        headers = {"Authorization": f"Bearer {token}"}
        return admin, headers

    def _make_user(self, db):
        user = User(
            email="user@test.com",
            name="User",
            password_hash=hash_password("password123"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def test_admin_get_registry(self, client, db):
        admin, headers = self._make_admin(db)
        response = client.get("/api/admin/features/registry", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "seo" in data
        assert "label" in data["seo"]
        assert "blocks" in data["seo"]

    def test_admin_get_user_features(self, client, db):
        admin, headers = self._make_admin(db)
        user = self._make_user(db)

        response = client.get(f"/api/admin/features/{user.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user.id
        assert isinstance(data["features"], dict)
        # NULL features = all true
        assert all(v is True for v in data["features"].values())

    def test_admin_update_features(self, client, db):
        admin, headers = self._make_admin(db)
        user = self._make_user(db)

        response = client.put(
            f"/api/admin/features/{user.id}",
            headers=headers,
            json={"features": {"seo": False, "geo.france_map": False}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["features"]["seo"] is False
        assert data["features"]["seo.serp_rankings"] is False  # cascade
        assert data["features"]["geo.france_map"] is False
        assert data["features"]["geo"] is True  # page still enabled

        # Verify persistence
        response2 = client.get(f"/api/admin/features/{user.id}", headers=headers)
        assert response2.json()["features"]["seo"] is False

    def test_admin_update_features_non_admin_forbidden(self, client, db):
        user = User(
            email="nonadmin@test.com",
            name="NotAdmin",
            password_hash=hash_password("password123"),
            is_admin=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.put(
            "/api/admin/features/1",
            headers=headers,
            json={"features": {"seo": False}},
        )
        assert response.status_code == 403

    def test_admin_update_features_invalid_user(self, client, db):
        admin, headers = self._make_admin(db)
        response = client.put(
            "/api/admin/features/9999",
            headers=headers,
            json={"features": {"seo": False}},
        )
        assert response.status_code == 404

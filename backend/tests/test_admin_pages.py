"""Tests for admin pages audit endpoints."""
from database import Competitor, Ad, AdvertiserCompetitor, User


class TestSectorsEndpoint:
    def test_admin_can_list_sectors(self, client, db, test_user, auth_headers):
        user, _ = test_user
        user.is_admin = True
        db.commit()
        resp = client.get("/api/admin/sectors", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(s["code"] == "supermarche" for s in data)

    def test_non_admin_forbidden(self, client, auth_headers):
        resp = client.get("/api/admin/sectors", headers=auth_headers)
        assert resp.status_code == 403


class TestPagesAudit:
    def test_admin_audit_all(self, client, db, test_user, auth_headers, test_competitor):
        user, _ = test_user
        user.is_admin = True
        db.commit()
        resp = client.get("/api/admin/pages-audit", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # At least one sector should contain our test competitor
        all_names = [c["name"] for s in data for c in s["competitors"]]
        assert "Carrefour" in all_names

    def test_admin_audit_filter_sector(self, client, db, test_user, auth_headers, test_competitor):
        user, _ = test_user
        user.is_admin = True
        db.commit()
        resp = client.get("/api/admin/pages-audit?sector=supermarche", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Should have at most supermarche sector
        codes = [s["code"] for s in data]
        assert all(c == "supermarche" for c in codes)

    def test_non_admin_forbidden(self, client, auth_headers):
        resp = client.get("/api/admin/pages-audit", headers=auth_headers)
        assert resp.status_code == 403

    def test_facebook_pages_detected(self, client, db, test_user, auth_headers, test_competitor):
        """Facebook ads with page_ids should appear in audit."""
        user, _ = test_user
        user.is_admin = True

        # Add some ads with page_ids
        ad1 = Ad(competitor_id=test_competitor.id, ad_id="fb_1", platform="facebook",
                 page_id="111", page_name="Carrefour France")
        ad2 = Ad(competitor_id=test_competitor.id, ad_id="fb_2", platform="facebook",
                 page_id="222", page_name="Carrefour Bio")
        db.add_all([ad1, ad2])
        db.commit()

        resp = client.get("/api/admin/pages-audit", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        carrefour = None
        for s in data:
            for c in s["competitors"]:
                if c["name"] == "Carrefour":
                    carrefour = c
                    break
        assert carrefour is not None
        fb = carrefour["platforms"]["facebook"]
        assert fb["total_pages"] == 2
        assert len(fb["detected_pages"]) == 2


class TestDeletePage:
    def test_delete_facebook_page(self, client, db, test_user, auth_headers, test_competitor):
        user, _ = test_user
        user.is_admin = True
        ad = Ad(competitor_id=test_competitor.id, ad_id="del_1", platform="facebook",
                page_id="999", page_name="Wrong Page")
        db.add(ad)
        db.commit()

        resp = client.post("/api/admin/pages-audit/delete", headers=auth_headers,
                           json={"competitor_id": test_competitor.id, "platform": "facebook", "page_id": "999"})
        assert resp.status_code == 200
        assert "supprimee" in resp.json()["action"].lower() or "supprimées" in resp.json()["action"].lower()

        # Verify ad is gone
        remaining = db.query(Ad).filter(Ad.ad_id == "del_1").first()
        assert remaining is None

    def test_delete_handle(self, client, db, test_user, auth_headers, test_competitor):
        user, _ = test_user
        user.is_admin = True
        test_competitor.instagram_username = "test_insta"
        db.commit()

        resp = client.post("/api/admin/pages-audit/delete", headers=auth_headers,
                           json={"competitor_id": test_competitor.id, "platform": "instagram"})
        assert resp.status_code == 200
        db.refresh(test_competitor)
        assert test_competitor.instagram_username is None

    def test_non_admin_forbidden(self, client, auth_headers, test_competitor):
        resp = client.post("/api/admin/pages-audit/delete", headers=auth_headers,
                           json={"competitor_id": test_competitor.id, "platform": "instagram"})
        assert resp.status_code == 403

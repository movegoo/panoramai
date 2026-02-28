"""Tests for Facebook child page discovery — Google Search strategy."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import json

# Import the validation function
from routers.facebook import _is_valid_child


class TestIsValidChild:
    """Test the _is_valid_child helper used across all strategies."""

    def test_exact_match(self):
        assert _is_valid_child("Intersport", "Intersport") is True

    def test_child_with_city(self):
        assert _is_valid_child("Intersport", "Intersport Briançon") is True

    def test_child_with_dash(self):
        assert _is_valid_child("Intersport", "Intersport - Annecy") is True

    def test_child_with_apostrophe(self):
        assert _is_valid_child("Leroy Merlin", "Leroy Merlin l'Isle-Adam") is True

    def test_unrelated_page(self):
        assert _is_valid_child("Intersport", "Nike France") is False

    def test_negative_keyword_blocks(self):
        assert _is_valid_child("Weldom", "Weldom Musée") is False

    def test_brand_prefix_leclerc(self):
        """E.Leclerc has known prefixes in BRAND_PREFIXES."""
        assert _is_valid_child("Leclerc", "E.Leclerc Béziers") is True

    def test_case_insensitive(self):
        assert _is_valid_child("Intersport", "intersport grenoble") is True

    def test_country_suffix_blocked(self):
        assert _is_valid_child("Intersport", "Intersport España") is False


class TestGoogleSearchStrategy:
    """Test the Google Search discovery strategy for child pages."""

    def test_facebook_url_extraction(self):
        """Verify regex extracts Facebook handles from various URL formats."""
        import re
        pattern = r'https?://(?:www\.|m\.|fr-fr\.)?facebook\.com/(?:p/)?([^/?#]+)'

        test_cases = [
            ("https://www.facebook.com/IntersportBriancon", "IntersportBriancon"),
            ("https://m.facebook.com/IntersportAnnecy", "IntersportAnnecy"),
            ("https://fr-fr.facebook.com/LeroyMerlinParis", "LeroyMerlinParis"),
            ("https://www.facebook.com/p/IntersportGrenoble", "IntersportGrenoble"),
            ("https://facebook.com/WeldomMontpellier?ref=123", "WeldomMontpellier"),
        ]
        for url, expected_handle in test_cases:
            match = re.match(pattern, url)
            assert match is not None, f"Failed to match {url}"
            assert match.group(1) == expected_handle, f"Expected {expected_handle}, got {match.group(1)}"

    def test_skip_non_page_urls(self):
        """Non-page Facebook URLs should be skipped."""
        import re
        pattern = r'https?://(?:www\.|m\.|fr-fr\.)?facebook\.com/(?:p/)?([^/?#]+)'
        skip_handles = {"watch", "events", "groups", "marketplace", "pages",
                        "profile.php", "story.php", "share", "login", "help",
                        "photo", "photos", "videos", "reel", "reels", "permalink.php"}

        skip_urls = [
            "https://www.facebook.com/watch/123",
            "https://www.facebook.com/events/456",
            "https://www.facebook.com/groups/intersport",
        ]
        for url in skip_urls:
            match = re.match(pattern, url)
            if match:
                assert match.group(1) in skip_handles, f"{url} should be skipped"

    @pytest.mark.asyncio
    async def test_google_search_finds_child_pages(self):
        """Full integration test: Google Search → profile fetch → child page found."""
        from routers.facebook import _discover_child_pages_background

        mock_google = AsyncMock(return_value={
            "success": True,
            "results": [
                {"url": "https://www.facebook.com/IntersportBriancon", "title": "Intersport Briançon - Sports Store"},
                {"url": "https://www.facebook.com/IntersportAnnecy", "title": "Intersport Annecy - Boutique"},
                {"url": "https://www.facebook.com/watch/some-video", "title": "Watch video"},
                {"url": "https://www.facebook.com/NikeFrance", "title": "Nike France - Officiel"},
            ],
        })

        mock_profile = AsyncMock(side_effect=[
            {"success": True, "page_id": "111222333", "name": "Intersport Briançon"},
            {"success": True, "page_id": "444555666", "name": "Intersport Annecy"},
        ])

        mock_search_companies = AsyncMock(return_value={"success": True, "companies": []})

        # Mock competitor
        mock_comp = MagicMock()
        mock_comp.id = 47
        mock_comp.name = "Intersport"
        mock_comp.facebook_page_id = "43767900785"
        mock_comp.child_page_ids = None

        # Mock DB — MagicMock auto-chains, but we need .all() to return
        # [mock_comp] on first call and [] on subsequent calls
        mock_db = MagicMock()
        # All chained query calls (.query().filter().all(), .query().filter().filter().distinct().all(), etc.)
        # resolve through MagicMock auto-chaining. We set .all() at multiple levels:
        all_mock = MagicMock(side_effect=[[mock_comp], [], []])
        # Patch all possible paths to .all()
        mock_db.query.return_value.filter.return_value.all = all_mock
        mock_db.query.return_value.filter.return_value.filter.return_value.all = MagicMock(return_value=[mock_comp])
        mock_db.query.return_value.filter.return_value.distinct.return_value.all = MagicMock(return_value=[])
        mock_db.query.return_value.filter.return_value.filter.return_value.distinct.return_value.all = MagicMock(return_value=[])
        mock_db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all = MagicMock(return_value=[])

        with patch("database.SessionLocal", return_value=mock_db):
            with patch("routers.facebook.scrapecreators") as mock_sc:
                mock_sc.search_google = mock_google
                mock_sc.fetch_facebook_profile = mock_profile
                mock_sc.search_facebook_companies = mock_search_companies

                await _discover_child_pages_background([47], 12)

        # Verify Google search was called
        mock_google.assert_called()
        # Verify profile was fetched for valid child pages (not watch, not Nike)
        assert mock_profile.call_count == 2

        # Verify child_page_ids were saved
        saved_children = json.loads(mock_comp.child_page_ids)
        assert "111222333" in saved_children
        assert "444555666" in saved_children
        assert len(saved_children) == 2

    @pytest.mark.asyncio
    async def test_google_search_skips_parent_page(self):
        """Google Search should not add the parent page as a child."""
        from routers.facebook import _discover_child_pages_background

        mock_google = AsyncMock(return_value={
            "success": True,
            "results": [
                {"url": "https://www.facebook.com/IntersportFrance", "title": "Intersport France - Officiel"},
            ],
        })

        mock_profile = AsyncMock(return_value={
            "success": True,
            "page_id": "43767900785",  # Same as parent
            "name": "Intersport France",
        })

        mock_search_companies = AsyncMock(return_value={"success": True, "companies": []})

        mock_comp = MagicMock()
        mock_comp.id = 47
        mock_comp.name = "Intersport"
        mock_comp.facebook_page_id = "43767900785"
        mock_comp.child_page_ids = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_comp]
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = []

        with patch("database.SessionLocal", return_value=mock_db):
            with patch("routers.facebook.scrapecreators") as mock_sc:
                mock_sc.search_google = mock_google
                mock_sc.fetch_facebook_profile = mock_profile
                mock_sc.search_facebook_companies = mock_search_companies

                await _discover_child_pages_background([47], 12)

        # Parent page should NOT be in children
        if mock_comp.child_page_ids:
            saved = json.loads(mock_comp.child_page_ids)
            assert "43767900785" not in saved

    @pytest.mark.asyncio
    async def test_google_search_deduplicates(self):
        """Same page found by Google and Ad Library should not be duplicated."""
        from routers.facebook import _discover_child_pages_background

        mock_google = AsyncMock(return_value={
            "success": True,
            "results": [
                {"url": "https://www.facebook.com/IntersportBriancon", "title": "Intersport Briançon"},
            ],
        })

        mock_profile = AsyncMock(return_value={
            "success": True,
            "page_id": "111222333",
            "name": "Intersport Briançon",
        })

        # Ad Library also finds the same page
        mock_search_companies = AsyncMock(return_value={
            "success": True,
            "companies": [{"page_id": "111222333", "name": "Intersport Briançon"}],
        })

        mock_comp = MagicMock()
        mock_comp.id = 47
        mock_comp.name = "Intersport"
        mock_comp.facebook_page_id = "43767900785"
        mock_comp.child_page_ids = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_comp]
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = []

        with patch("database.SessionLocal", return_value=mock_db):
            with patch("routers.facebook.scrapecreators") as mock_sc:
                mock_sc.search_google = mock_google
                mock_sc.fetch_facebook_profile = mock_profile
                mock_sc.search_facebook_companies = mock_search_companies

                await _discover_child_pages_background([47], 12)

        # Should only have one entry, not duplicated
        if mock_comp.child_page_ids:
            saved = json.loads(mock_comp.child_page_ids)
            assert saved.count("111222333") == 1


class TestFetchFacebookProfilePageId:
    """Test that fetch_facebook_profile now returns page_id."""

    @pytest.mark.asyncio
    async def test_profile_returns_page_id(self):
        from services.scrapecreators import ScrapeCreatorsAPI

        api = ScrapeCreatorsAPI(api_key="test")
        mock_response = {
            "success": True,
            "pageId": "123456789",
            "name": "Intersport Briançon",
            "followerCount": 1500,
            "likeCount": 1200,
        }

        with patch.object(api, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await api.fetch_facebook_profile("https://facebook.com/IntersportBriancon")

        assert result["success"] is True
        assert result["page_id"] == "123456789"
        assert result["name"] == "Intersport Briançon"

    @pytest.mark.asyncio
    async def test_profile_no_page_id(self):
        """When API doesn't return page_id, field should be empty string."""
        from services.scrapecreators import ScrapeCreatorsAPI

        api = ScrapeCreatorsAPI(api_key="test")
        mock_response = {
            "success": True,
            "name": "Intersport Briançon",
            "followerCount": 1500,
        }

        with patch.object(api, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await api.fetch_facebook_profile("https://facebook.com/IntersportBriancon")

        assert result["success"] is True
        assert result["page_id"] == ""

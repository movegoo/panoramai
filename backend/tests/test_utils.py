"""Tests for core/utils.py"""
from core.utils import get_logo_url


class TestGetLogoUrl:
    def test_valid_website(self):
        result = get_logo_url("carrefour.fr")
        assert result == "https://www.google.com/s2/favicons?domain=carrefour.fr&sz=128"

    def test_with_https(self):
        result = get_logo_url("https://carrefour.fr")
        assert result == "https://www.google.com/s2/favicons?domain=carrefour.fr&sz=128"

    def test_with_http(self):
        result = get_logo_url("http://carrefour.fr")
        assert result == "https://www.google.com/s2/favicons?domain=carrefour.fr&sz=128"

    def test_with_www(self):
        result = get_logo_url("https://www.carrefour.fr")
        assert result == "https://www.google.com/s2/favicons?domain=carrefour.fr&sz=128"

    def test_with_path(self):
        result = get_logo_url("https://www.carrefour.fr/some/path")
        assert result == "https://www.google.com/s2/favicons?domain=carrefour.fr&sz=128"

    def test_none(self):
        assert get_logo_url(None) is None

    def test_empty_string(self):
        assert get_logo_url("") is None

    def test_no_tld(self):
        assert get_logo_url("localhost") is None

    def test_no_tld_with_scheme(self):
        assert get_logo_url("https://localhost") is None

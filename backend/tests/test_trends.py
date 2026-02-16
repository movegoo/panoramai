"""Tests for core/trends.py"""
from core.trends import calculate_trend, parse_download_count, TrendDirection


class TestCalculateTrend:
    def test_upward(self):
        result = calculate_trend(150.0, 100.0)
        assert result["direction"] == TrendDirection.UP
        assert result["value"] == 50.0
        assert result["percent"] == 50.0

    def test_downward(self):
        result = calculate_trend(80.0, 100.0)
        assert result["direction"] == TrendDirection.DOWN
        assert result["value"] == -20.0
        assert result["percent"] == -20.0

    def test_stable(self):
        result = calculate_trend(100.0, 100.0)
        assert result["direction"] == TrendDirection.STABLE
        assert result["value"] == 0
        assert result["percent"] == 0.0

    def test_current_none(self):
        result = calculate_trend(None, 100.0)
        assert result["direction"] == TrendDirection.STABLE
        assert result["value"] == 0

    def test_previous_none(self):
        result = calculate_trend(100.0, None)
        assert result["direction"] == TrendDirection.STABLE
        assert result["value"] == 0

    def test_previous_zero(self):
        result = calculate_trend(100.0, 0)
        assert result["direction"] == TrendDirection.STABLE
        assert result["value"] == 0

    def test_both_none(self):
        result = calculate_trend(None, None)
        assert result["direction"] == TrendDirection.STABLE


class TestParseDownloadCount:
    def test_french_spaces(self):
        assert parse_download_count("1 000 000+") == 1_000_000

    def test_suffix_m(self):
        assert parse_download_count("10M+") == 10_000_000

    def test_suffix_k(self):
        assert parse_download_count("500K+") == 500_000

    def test_suffix_b(self):
        assert parse_download_count("1B+") == 1_000_000_000

    def test_none(self):
        assert parse_download_count(None) == 0

    def test_empty_string(self):
        assert parse_download_count("") == 0

    def test_garbage(self):
        assert parse_download_count("not a number") == 0

    def test_plain_number(self):
        assert parse_download_count("5000") == 5000

    def test_narrow_no_break_space(self):
        assert parse_download_count("1\u202f000\u202f000+") == 1_000_000

    def test_non_breaking_space(self):
        assert parse_download_count("1\u00a0000\u00a0000+") == 1_000_000

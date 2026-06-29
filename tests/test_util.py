"""Tests for visage.util — formatting utilities and DeltaTracker."""

from visage.util import (
    DeltaTracker,
    format_bytes,
    format_percent,
    format_rate,
    shorten_name,
)


class TestFormatBytes:
    def test_bytes(self):
        assert format_bytes(0) == "0 B"
        assert format_bytes(500) == "500 B"
        assert format_bytes(999) == "999 B"

    def test_kilobytes(self):
        assert format_bytes(1_000) == "1 KB"
        assert format_bytes(1_500) == "2 KB"
        assert format_bytes(999_999) == "1000 KB"

    def test_megabytes(self):
        assert format_bytes(1_000_000) == "1 MB"
        assert format_bytes(10_000_000) == "10 MB"

    def test_gigabytes(self):
        assert format_bytes(1_000_000_000) == "1.0 GB"
        assert format_bytes(2_500_000_000) == "2.5 GB"


class TestFormatRate:
    def test_bytes_per_sec(self):
        assert format_rate(0) == "0 B/s"
        assert format_rate(500) == "500 B/s"

    def test_kilobytes_per_sec(self):
        assert format_rate(1_000) == "1 KB/s"
        assert format_rate(1_500) == "2 KB/s"

    def test_megabytes_per_sec(self):
        assert format_rate(1_000_000) == "1 MB/s"
        assert format_rate(10_000_000) == "10 MB/s"

    def test_gigabytes_per_sec(self):
        assert format_rate(1_000_000_000) == "1.0 GB/s"
        assert format_rate(2_500_000_000) == "2.5 GB/s"


class TestFormatPercent:
    def test_format(self):
        assert format_percent(50.0) == "50.0%"
        assert format_percent(0.0) == "0.0%"
        assert format_percent(100.0) == "100.0%"
        assert format_percent(33.333) == "33.3%"


class TestShortenName:
    def test_short_name(self):
        assert shorten_name("hello") == "hello"

    def test_exact_max(self):
        assert shorten_name("a" * 18) == "a" * 18

    def test_truncated(self):
        assert shorten_name("a" * 20) == "a" * 17 + "\u2026"

    def test_custom_max_len(self):
        assert shorten_name("hello world", max_len=5) == "hell\u2026"


class TestDeltaTracker:
    def test_first_update_returns_zeros(self):
        dt = DeltaTracker()
        result = dt.update({"a": 10.0, "b": 20.0})
        assert result == {"a": 0.0, "b": 0.0}

    def test_second_update_returns_deltas(self):
        dt = DeltaTracker()
        dt.update({"a": 10.0, "b": 20.0})
        result = dt.update({"a": 15.0, "b": 25.0})
        assert result == {"a": 5.0, "b": 5.0}

    def test_delta_wraps_to_zero_on_reset(self):
        dt = DeltaTracker()
        dt.update({"a": 100.0})
        result = dt.update({"a": 50.0})
        assert result["a"] == -50.0

    def test_new_key_in_second_update(self):
        dt = DeltaTracker()
        dt.update({"a": 10.0})
        result = dt.update({"a": 15.0, "b": 5.0})
        assert result["a"] == 5.0
        assert result["b"] == 0.0  # first time seeing "b"

    def test_missing_key_in_second_update(self):
        dt = DeltaTracker()
        dt.update({"a": 10.0, "b": 20.0})
        result = dt.update({"a": 15.0})
        assert "b" not in result

    def test_converts_int_values_to_float(self):
        dt = DeltaTracker()
        result = dt.update({"a": 10, "b": 20})
        for v in result.values():
            assert isinstance(v, float)

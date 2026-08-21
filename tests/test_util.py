"""Tests for visage.util — formatting utilities and DeltaTracker."""

from visage.util import (
    DeltaTracker,
    HistoryBuffer,
    format_bytes,
    format_percent,
    format_rate,
    render_block_graph,
    render_braille_graph,
    render_sparkline,
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
        result = dt.update({"a": 10.0, "b": 20.0}, now=100.0)
        assert result == {"a": 0.0, "b": 0.0}

    def test_second_update_returns_per_second_rates(self):
        dt = DeltaTracker()
        dt.update({"a": 10.0, "b": 20.0}, now=100.0)
        result = dt.update({"a": 15.0, "b": 25.0}, now=105.0)
        assert result == {"a": 1.0, "b": 1.0}  # 5 units over 5s

    def test_rate_scales_with_elapsed_time(self):
        dt = DeltaTracker()
        dt.update({"a": 0.0}, now=0.0)
        result = dt.update({"a": 100.0}, now=4.0)
        assert result["a"] == 25.0

    def test_counter_reset_clamps_to_zero(self):
        dt = DeltaTracker()
        dt.update({"a": 100.0}, now=1.0)
        result = dt.update({"a": 50.0}, now=2.0)
        assert result["a"] == 0.0

    def test_zero_elapsed_time_returns_zeros(self):
        dt = DeltaTracker()
        dt.update({"a": 10.0}, now=5.0)
        result = dt.update({"a": 15.0}, now=5.0)
        assert result["a"] == 0.0

    def test_new_key_in_second_update(self):
        dt = DeltaTracker()
        dt.update({"a": 10.0}, now=1.0)
        result = dt.update({"a": 15.0, "b": 5.0}, now=2.0)
        assert result["a"] == 5.0
        assert result["b"] == 0.0  # first time seeing "b"

    def test_missing_key_in_second_update(self):
        dt = DeltaTracker()
        dt.update({"a": 10.0, "b": 20.0}, now=1.0)
        result = dt.update({"a": 15.0}, now=2.0)
        assert "b" not in result

    def test_converts_int_values_to_float(self):
        dt = DeltaTracker()
        result = dt.update({"a": 10, "b": 20})
        for v in result.values():
            assert isinstance(v, float)

    def test_defaults_to_monotonic_clock(self):
        dt = DeltaTracker()
        dt.update({"a": 0.0})
        result = dt.update({"a": 1.0})
        assert isinstance(result["a"], float)
        assert result["a"] >= 0.0


class TestRenderSparkline:
    def test_empty(self):
        assert render_sparkline([]) == ""

    def test_single_value(self):
        assert render_sparkline([0.5]) == "\u2588"

    def test_width_one_no_divide_by_zero(self):
        assert render_sparkline([0.0, 0.5, 1.0], width=1) == "\u2581"

    def test_zero_width_returns_empty(self):
        assert render_sparkline([0.5, 1.0], width=0) == ""

    def test_width_wider_than_data_clamps(self):
        out = render_sparkline([0.0, 0.5, 1.0], width=15)
        assert len(out) == 3

    def test_normal_range_has_expected_length(self):
        out = render_sparkline([0.1, 0.4, 0.7, 1.0, 0.0, 0.6, 0.9], width=5)
        assert len(out) == 5

    def test_all_values_in_charset(self):
        out = render_sparkline([0.0, 0.25, 0.5, 0.75, 1.0], width=5)
        for ch in out:
            assert "\u2581" <= ch <= "\u2588"


class TestHistoryBuffer:
    def test_capacity_limited(self):
        buf = HistoryBuffer(3)
        for v in (1, 2, 3, 4, 5):
            buf.push(v)
        assert buf.values == [3, 4, 5]
        assert buf.full

    def test_normalize_empty(self):
        assert HistoryBuffer().normalize() == []

    def test_normalize_flat_series(self):
        buf = HistoryBuffer(3)
        for _ in range(3):
            buf.push(5.0)
        assert buf.normalize() == [0.0, 0.0, 0.0]

    def test_normalize_pct_empty(self):
        assert HistoryBuffer().normalize_pct() == []

    def test_normalize_pct_clamps_at_100(self):
        buf = HistoryBuffer(3)
        buf.push(50.0)
        buf.push(100.0)
        buf.push(150.0)
        result = buf.normalize_pct()
        assert result == [0.5, 1.0, 1.0]

    def test_normalize_pct_zero_values(self):
        buf = HistoryBuffer(3)
        buf.push(0.0)
        buf.push(0.0)
        buf.push(0.0)
        assert buf.normalize_pct() == [0.0, 0.0, 0.0]

    def test_normalize_pct_single_value(self):
        buf = HistoryBuffer(1)
        buf.push(75.0)
        assert buf.normalize_pct() == [0.75]


class TestRenderBrailleGraph:
    def test_empty(self):
        assert render_braille_graph([]) == ""

    def test_single_value(self):
        result = render_braille_graph([0.5], width=1, height=1)
        assert len(result) > 0

    def test_zero_dimensions(self):
        assert render_braille_graph([0.5], width=0, height=1) == ""
        assert render_braille_graph([0.5], width=1, height=0) == ""

    def test_full_height_fill(self):
        result = render_braille_graph([1.0, 1.0, 1.0], width=3, height=2)
        lines = result.split("\n")
        assert len(lines) == 2

    def test_width_clamped_to_data(self):
        result = render_braille_graph([0.5, 0.8], width=10, height=2)
        lines = result.split("\n")
        for line in lines:
            assert len(line) == 2

    def test_returns_string(self):
        result = render_braille_graph([0.1, 0.3, 0.5, 0.7, 0.9], width=5, height=3)
        assert isinstance(result, str)
        assert "\n" in result


class TestRenderBlockGraph:
    def test_empty(self):
        assert render_block_graph([]) == ""

    def test_single_value(self):
        result = render_block_graph([0.5], width=1, height=1)
        assert len(result) > 0

    def test_zero_dimensions(self):
        assert render_block_graph([0.5], width=0, height=1) == ""
        assert render_block_graph([0.5], width=1, height=0) == ""

    def test_full_height_fill(self):
        result = render_block_graph([1.0, 1.0, 1.0], width=3, height=2)
        lines = result.split("\n")
        assert len(lines) == 2
        for line in lines:
            assert "\u2588" in line

    def test_empty_fill(self):
        result = render_block_graph([0.0, 0.0], width=2, height=1)
        lines = result.split("\n")
        assert len(lines) == 1
        assert lines[0] == "  "

    def test_half_fill(self):
        result = render_block_graph([0.5], width=1, height=1)
        lines = result.split("\n")
        assert len(lines) == 1
        assert "\u2584" in lines[0]

    def test_width_clamped_to_data(self):
        result = render_block_graph([0.5, 0.8], width=10, height=2)
        lines = result.split("\n")
        for line in lines:
            assert len(line) == 2

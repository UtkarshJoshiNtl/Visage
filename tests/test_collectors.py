"""Tests for visage collectors — parse logic and edge cases."""

from visage.collectors.cpu import _parse_jiffies


class TestCpuParseJiffies:
    def test_typical_line(self):
        line = "cpu  12345 0 6789 1000 500 0 0 0 0 0"
        total, idle = _parse_jiffies(line)
        assert total == 12345 + 0 + 6789 + 1000 + 500
        assert idle == 1000 + 500

    def test_all_zeros(self):
        line = "cpu  0 0 0 0 0 0 0 0 0 0"
        total, idle = _parse_jiffies(line)
        assert total == 0
        assert idle == 0

    def test_only_idle_nonzero(self):
        line = "cpu  0 0 0 100 200"
        total, idle = _parse_jiffies(line)
        assert total == 300
        assert idle == 300

    def test_no_idle(self):
        line = "cpu  100 200 300 0 0"
        total, idle = _parse_jiffies(line)
        assert total == 600
        assert idle == 0

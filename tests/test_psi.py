"""Tests for visage.collectors.psi — PSI metric parsing."""

from unittest.mock import mock_open, patch

from visage.collectors.psi import _parse_psi_line, _read_psi_file, collect


class TestParsePsiLine:
    def test_typical_some_line(self):
        line = "some avg10=0.50 avg60=0.30 avg300=0.10 total=12345"
        result = _parse_psi_line(line)
        assert result["avg10"] == 0.50
        assert result["avg60"] == 0.30
        assert result["avg300"] == 0.10
        assert result["total"] == 12345.0

    def test_typical_full_line(self):
        line = "full avg10=1.20 avg60=0.80 avg300=0.40 total=67890"
        result = _parse_psi_line(line)
        assert result["avg10"] == 1.20
        assert result["avg60"] == 0.80
        assert result["avg300"] == 0.40
        assert result["total"] == 67890.0

    def test_zero_values(self):
        line = "some avg10=0.00 avg60=0.00 avg300=0.00 total=0"
        result = _parse_psi_line(line)
        assert result["avg10"] == 0.0
        assert result["total"] == 0.0

    def test_empty_line(self):
        result = _parse_psi_line("")
        assert result == {}


class TestReadPsiFile:
    def test_valid_file(self):
        content = "some avg10=0.50 avg60=0.30 avg300=0.10 total=12345\nfull avg10=1.00 avg60=0.50 avg300=0.20 total=67890\n"
        with patch("builtins.open", mock_open(read_data=content)):
            result = _read_psi_file("/proc/pressure/memory")
        assert "some" in result
        assert "full" in result
        assert result["some"]["avg10"] == 0.50
        assert result["full"]["avg10"] == 1.00

    def test_missing_file(self):
        with patch("builtins.open", side_effect=OSError("No such file")):
            result = _read_psi_file("/proc/pressure/cpu")
        assert result == {}

    def test_cpu_only_some(self):
        content = "some avg10=2.50 avg60=1.00 avg300=0.50 total=99999\n"
        with patch("builtins.open", mock_open(read_data=content)):
            result = _read_psi_file("/proc/pressure/cpu")
        assert "some" in result
        assert "full" not in result


class TestCollectPsi:
    def test_non_linux_returns_unavailable(self):
        with patch("visage.collectors.psi.sys.platform", "darwin"):
            result = collect()
            assert result["available"] is False
            assert result["cpu"] == {}

    def test_linux_reads_all_resources(self):
        cpu_content = "some avg10=0.10 avg60=0.05 avg300=0.01 total=100\n"
        mem_content = "some avg10=0.20 avg60=0.10 avg300=0.05 total=200\nfull avg10=0.10 avg60=0.05 avg300=0.02 total=100\n"
        io_content = "some avg10=0.30 avg60=0.15 avg300=0.08 total=300\nfull avg10=0.25 avg60=0.12 avg300=0.06 total=250\n"

        def mock_open_func(path, *args, **kwargs):
            from io import StringIO
            contents = {
                "/proc/pressure/cpu": cpu_content,
                "/proc/pressure/memory": mem_content,
                "/proc/pressure/io": io_content,
            }
            return StringIO(contents.get(path, ""))

        with patch("visage.collectors.psi.sys.platform", "linux"), \
             patch("builtins.open", side_effect=mock_open_func):
            result = collect()

        assert result["available"] is True
        assert result["cpu"]["some"]["avg10"] == 0.10
        assert result["memory"]["some"]["avg10"] == 0.20
        assert result["memory"]["full"]["avg10"] == 0.10
        assert result["io"]["some"]["avg10"] == 0.30
        assert result["io"]["full"]["avg10"] == 0.25

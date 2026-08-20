"""Tests for Sprint 10 — export, API, packaging."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


class TestExportEnhanced:
    def test_export_json(self):
        from visage.export.exporter import export_json
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        result = export_json({"cpu": 50.0, "mem": 75.0}, path)
        assert result.exists()
        data = json.loads(result.read_text())
        assert "timestamp" in data
        assert data["cpu"] == 50.0
        assert data["mem"] == 75.0
        Path(path).unlink()

    def test_export_json_lines(self):
        from visage.export.exporter import export_json_lines
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        export_json_lines(path, {"cpu": 50.0})
        export_json_lines(path, {"cpu": 60.0})
        lines = Path(path).read_text().strip().split("\n")
        assert len(lines) == 2
        d1 = json.loads(lines[0])
        d2 = json.loads(lines[1])
        assert d1["cpu"] == 50.0
        assert d2["cpu"] == 60.0
        Path(path).unlink()

    def test_export_csv(self):
        from visage.export.exporter import export_csv
        path = Path(tempfile.mktemp(suffix=".csv"))
        rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = export_csv(rows, path)
        assert result.exists()
        content = result.read_text()
        assert "a,b" in content
        assert "1,2" in content
        path.unlink()

    def test_export_log(self):
        from visage.export.exporter import export_log
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            path = f.name
        export_log("test message", path)
        content = Path(path).read_text()
        assert "test message" in content
        assert "[" in content
        Path(path).unlink()

    def test_prometheus_format(self):
        from visage.export.exporter import prometheus_format
        metrics = {"cpu_percent": 50.0, "memory_used": 1024}
        result = prometheus_format(metrics)
        assert "visage_cpu_percent 50.0" in result
        assert "visage_memory_used 1024" in result

    def test_prometheus_format_nested(self):
        from visage.export.exporter import prometheus_format
        metrics = {"disk": {"read_bytes": 1000, "write_bytes": 2000}}
        result = prometheus_format(metrics)
        assert "visage_disk_read_bytes 1000" in result
        assert "visage_disk_write_bytes 2000" in result

    def test_prometheus_format_empty(self):
        from visage.export.exporter import prometheus_format
        result = prometheus_format({})
        assert result == ""


class TestCLI:
    def test_version_flag(self):
        from visage.__main__ import main
        with patch("sys.argv", ["visage", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_export_format_jsonl(self):
        from visage.__main__ import _run_export
        with patch("visage.export.exporter.export_json_lines") as mock_export:
            mock_export.return_value = Path("/tmp/test.jsonl")
            _run_export("/tmp/test.jsonl", "jsonl")
            mock_export.assert_called_once()

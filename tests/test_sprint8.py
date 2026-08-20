"""Tests for Sprint 8 — sensors, network, and per-process network."""

import sys
from unittest.mock import MagicMock, patch
import pytest


class TestSensorsCollect:
    def test_collect_temperatures_empty(self):
        from visage.collectors.sensors import collect_temperatures
        with patch("visage.collectors.sensors.psutil.sensors_temperatures", return_value=None):
            result = collect_temperatures()
            assert result["available"] is False
            assert result["entries"] == []

    def test_collect_temperatures_with_data(self):
        from visage.collectors.sensors import collect_temperatures
        mock_sensor = MagicMock(label="Core 0", current=65.0, high=80.0, critical=100.0)
        with patch("visage.collectors.sensors.psutil.sensors_temperatures", return_value={"coretemp": [mock_sensor]}):
            result = collect_temperatures()
            assert result["available"] is True
            assert len(result["entries"]) == 1
            assert result["entries"][0]["label"] == "Core 0"
            assert result["entries"][0]["current"] == 65.0

    def test_collect_temperatures_empty_label_uses_name(self):
        from visage.collectors.sensors import collect_temperatures
        mock_sensor = MagicMock(label="", current=50.0, high=80.0, critical=100.0)
        with patch("visage.collectors.sensors.psutil.sensors_temperatures", return_value={"coretemp": [mock_sensor]}):
            result = collect_temperatures()
            assert result["entries"][0]["label"] == "coretemp"

    def test_collect_fans_no_hwmon(self):
        from visage.collectors.sensors import collect_fans
        with patch("visage.collectors.sensors.Path") as MockPath:
            MockPath.return_value.exists.return_value = False
            result = collect_fans()
            assert result["available"] is False

    def test_collect_power_no_sysfs(self):
        from visage.collectors.sensors import collect_power
        with patch("visage.collectors.sensors.Path") as MockPath:
            MockPath.return_value.exists.return_value = False
            result = collect_power()
            assert result["available"] is False

    def test_collect_all(self):
        from visage.collectors.sensors import collect
        with patch("visage.collectors.sensors.collect_temperatures", return_value={"available": True, "entries": []}), \
             patch("visage.collectors.sensors.collect_fans", return_value={"available": False, "entries": []}), \
             patch("visage.collectors.sensors.collect_power", return_value={"available": False, "entries": []}):
            result = collect()
            assert "temperatures" in result
            assert "fans" in result
            assert "power" in result


class TestNetworkCollect:
    def test_collect_basic(self):
        from visage.collectors.network import collect
        result = collect()
        assert "total" in result
        assert "pernic" in result
        assert isinstance(result["total"], dict)
        assert isinstance(result["pernic"], dict)

    def test_collect_skips_loopback(self):
        from visage.collectors.network import collect
        result = collect()
        assert "lo" not in result["pernic"]

    def test_collect_per_nic_has_fields(self):
        from visage.collectors.network import collect
        result = collect()
        for name, info in result["pernic"].items():
            assert "ip" in info
            assert "bytes_sent" in info
            assert "bytes_recv" in info


class TestPerProcessNetwork:
    @pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
    def test_collect_per_process_returns_list(self):
        from visage.collectors.network import collect_per_process
        result = collect_per_process(top_n=5)
        assert isinstance(result, list)
        assert len(result) <= 5

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
    def test_collect_per_process_has_fields(self):
        from visage.collectors.network import collect_per_process
        result = collect_per_process(top_n=5)
        for entry in result:
            assert "pid" in entry
            assert "name" in entry
            assert "rx_bytes_est" in entry
            assert "tx_bytes_est" in entry
            assert "cpu_share" in entry

"""Tests for visage collectors — parse logic and edge cases."""

from visage.collectors.cpu import _parse_jiffies
from visage.collectors.gpu import EMPTY_RESULT, collect, _find_spec, _compute_roofline


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


class TestGpuFindSpec:
    def test_ada_pattern(self):
        spec = _find_spec("NVIDIA RTX 4090")
        assert spec["flops_fp32"] == 256
        assert spec["flops_fp16"] == 512
        assert spec["bus_width"] == 384

    def test_hopper_pattern(self):
        spec = _find_spec("NVIDIA H100 80GB HBM3")
        assert spec["flops_fp32"] == 256
        assert spec["bus_width"] == 5120

    def test_ampere_pattern(self):
        spec = _find_spec("NVIDIA A100 80GB")
        assert spec["flops_fp32"] == 128
        assert spec["bus_width"] == 5120

    def test_unknown_fallback(self):
        spec = _find_spec("Some Really Old GPU")
        assert spec == {"flops_fp32": 128, "flops_fp16": 256, "bus_width": 256}


class TestGpuRooflineMath:
    def test_a100_roofline(self):
        spec = {"flops_fp32": 128, "flops_fp16": 256, "bus_width": 5120}
        data = {
            "clock_core_mhz": 1410,
            "clock_mem_mhz": 1593,
            "sm_util": 80.0,
            "mem_util": 60.0,
            "sm_count": 108,
        }
        rl = _compute_roofline(data, spec)

        expected_fp32 = 108 * (1410 / 1000.0) * 128
        assert abs(rl["gflops_peak_fp32"] - expected_fp32) < 0.1

        bus_bytes = 5120 // 8
        expected_bw = 1593 * bus_bytes * 2 / 1000.0
        assert abs(rl["gbw_theoretical"] - expected_bw) < 0.1

        assert abs(rl["gflops_achieved"] - expected_fp32 * 0.80) < 0.1
        assert abs(rl["gbw_achieved"] - expected_bw * 0.60) < 0.1

        assert rl["arith_intensity"] > 0
        assert rl["ridge_point"] > 0
        assert rl["bound_by"] in ("Compute", "Memory")

    def test_idle_gpu(self):
        spec = {"flops_fp32": 128, "flops_fp16": 256, "bus_width": 256}
        data = {
            "clock_core_mhz": 210,
            "clock_mem_mhz": 405,
            "sm_util": 2.0,
            "mem_util": 3.0,
            "sm_count": 20,
        }
        rl = _compute_roofline(data, spec)
        assert rl["bound_by"] == "Idle"

    def test_zero_clocks(self):
        spec = {"flops_fp32": 128, "flops_fp16": 256, "bus_width": 256}
        data = {
            "clock_core_mhz": 0,
            "clock_mem_mhz": 0,
            "sm_util": 50.0,
            "mem_util": 50.0,
            "sm_count": 20,
        }
        rl = _compute_roofline(data, spec)
        assert rl["gflops_peak_fp32"] == 0.0
        assert rl["gbw_theoretical"] == 0.0
        assert rl["bound_by"] == "Idle"

    def test_no_gpu_fallback(self):
        result = collect()
        assert result["available"] is False
        assert result == EMPTY_RESULT

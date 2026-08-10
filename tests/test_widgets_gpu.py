"""Tests for GPU widget threshold handling — config keys map to widget keys."""

from visage.widgets.gpu import GpuWidget


class TestGpuWidgetThresholds:
    def test_defaults_present(self):
        w = GpuWidget()
        assert w._th["sm_util"] == {"red": 80, "yellow": 50}

    def test_config_prefixed_keys_are_applied(self):
        w = GpuWidget()
        w.set_thresholds({
            "gpu_sm_util": {"red": 90, "yellow": 60},
            "gpu_mem_util": {"red": 85},
            "gpu_temp_c": {"red": 88, "yellow": 72},
            "gpu_power_w": {"red": 95},
        })
        assert w._th["sm_util"] == {"red": 90, "yellow": 60}
        assert w._th["mem_util"] == {"red": 85, "yellow": 50}
        assert w._th["temp_c"] == {"red": 88, "yellow": 72}
        assert w._th["power_w"] == {"red": 95, "yellow": 75}

    def test_plain_keys_still_work(self):
        w = GpuWidget()
        w.set_thresholds({"sm_util": {"red": 70, "yellow": 40}})
        assert w._th["sm_util"] == {"red": 70, "yellow": 40}

    def test_unknown_keys_ignored(self):
        w = GpuWidget()
        w.set_thresholds({"bogus": {"red": 1}})
        assert w._th["sm_util"] == {"red": 80, "yellow": 50}

    def test_partial_merge_keeps_defaults(self):
        w = GpuWidget()
        w.set_thresholds({"gpu_temp_c": {"red": 95}})
        assert w._th["temp_c"] == {"red": 95, "yellow": 70}

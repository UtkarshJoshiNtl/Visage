"""Tests for visage.alert — rule evaluation, cooldowns, action dispatch."""

from visage.alert import AlertEngine


class TestAlertEngine:
    def test_gt_rule_triggers(self):
        fired: list[str] = []
        eng = AlertEngine()
        eng.set_rules([
            {"name": "cpu", "metric": "cpu_percent", "op": "gt",
             "value": 80, "message": "cpu {value}"},
        ])
        eng.set_action(fired.append)
        eng.evaluate({"cpu_percent": 90.0})
        assert fired == ["cpu 90.0"]

    def test_lt_rule_no_trigger(self):
        fired: list[str] = []
        eng = AlertEngine()
        eng.set_rules([
            {"name": "cpu", "metric": "cpu_percent", "op": "lt",
             "value": 80, "message": "cpu {value}"},
        ])
        eng.set_action(fired.append)
        eng.evaluate({"cpu_percent": 90.0})
        assert fired == []

    def test_cooldown_suppresses_repeats(self):
        fired: list[str] = []
        eng = AlertEngine()
        eng.set_rules([
            {"name": "cpu", "metric": "cpu_percent", "op": "gt",
             "value": 80, "cooldown": 60, "message": "cpu {value}"},
        ])
        eng.set_action(fired.append)
        eng.evaluate({"cpu_percent": 90.0})
        eng.evaluate({"cpu_percent": 95.0})
        assert len(fired) == 1

    def test_missing_metric_skipped(self):
        fired: list[str] = []
        eng = AlertEngine()
        eng.set_rules([
            {"name": "gpu", "metric": "gpu_sm_util", "op": "gt",
             "value": 80, "message": "gpu"},
        ])
        eng.set_action(fired.append)
        eng.evaluate({"cpu_percent": 90.0})
        assert fired == []

    def test_message_placeholder_replaced(self):
        fired: list[str] = []
        eng = AlertEngine()
        eng.set_rules([
            {"name": "mem", "metric": "mem_percent", "op": "gte",
             "value": 75, "message": "memory at {value}%"},
        ])
        eng.set_action(fired.append)
        eng.evaluate({"mem_percent": 81.25})
        assert fired == ["memory at 81.2%"]

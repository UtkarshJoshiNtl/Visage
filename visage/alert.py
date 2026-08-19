"""Alert engine — checks thresholds against collector snapshots with history."""

import time
from typing import Any, Callable

AlertAction = Callable[[str], None]


class AlertEngine:
    """Evaluates alert rules against a flat metric snapshot.

    Rules are defined in the config file as::

        {"name": "...", "metric": "...", "op": "gt|lt|gte|lte",
         "value": 42, "cooldown": 60, "message": "..."}

    Alert history is stored as a list of (timestamp, name, message) tuples.
    """

    def __init__(self) -> None:
        self._rules: list[dict[str, Any]] = []
        self._last_fired: dict[str, float] = {}
        self._action: AlertAction | None = None
        self._history: list[dict[str, Any]] = []
        self._max_history = 50

    def set_rules(self, rules: list[dict[str, Any]]) -> None:
        self._rules = rules

    def set_action(self, action: AlertAction) -> None:
        self._action = action

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

    def evaluate(self, snapshot: dict[str, Any]) -> None:
        now = time.monotonic()
        for rule in self._rules:
            name = rule.get("name", "")
            metric = rule.get("metric", "")
            op = rule.get("op", "gt")
            threshold = rule.get("value", 0)
            cooldown = rule.get("cooldown", 60)
            message = rule.get("message", f"Alert: {metric}")

            last = self._last_fired.get(name, 0.0)
            if now - last < cooldown:
                continue

            val = snapshot.get(metric)
            if val is None:
                continue

            trigger = False
            if op == "gt" and val > threshold:
                trigger = True
            elif op == "lt" and val < threshold:
                trigger = True
            elif op == "gte" and val >= threshold:
                trigger = True
            elif op == "lte" and val <= threshold:
                trigger = True

            if trigger:
                self._last_fired[name] = now
                msg = message.replace("{value}", f"{val:.1f}")
                self._history.append({
                    "time": time.time(),
                    "name": name,
                    "message": msg,
                    "metric": metric,
                    "value": val,
                    "threshold": threshold,
                })
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]
                if self._action:
                    self._action(msg)

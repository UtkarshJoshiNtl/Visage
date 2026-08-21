"""Configuration loader — zero-dependency, stdlib json only."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VisageConfig:
    refresh_interval: float = 1.0
    enabled_widgets: list[str] = field(default_factory=lambda: [
        "cpu", "memory", "disk", "network", "gpu", "psi", "sensors", "battery", "docker", "processes",
    ])
    widget_order: list[str] = field(default_factory=lambda: [
        "cpu", "memory", "disk", "network", "gpu", "psi", "sensors", "battery", "docker", "processes",
    ])
    thresholds: dict[str, Any] = field(default_factory=lambda: {
        "cpu": {"red": 80, "yellow": 50},
        "gpu_sm_util": {"red": 80, "yellow": 50},
        "gpu_mem_util": {"red": 80, "yellow": 50},
        "gpu_temp_c": {"red": 85, "yellow": 70},
        "gpu_power_w": {"red": 90, "yellow": 75},
        "memory": {"red": 90, "yellow": 75},
    })
    gpu_arch_override: dict[str, Any] | None = None
    alerts: list[dict[str, Any]] = field(default_factory=list)
    theme: str = "default"
    graph_style: str = "braille"

    @classmethod
    def defaults(cls) -> "VisageConfig":
        return cls()


def resolve_config_path(custom: str | None = None) -> Path | None:
    if custom:
        p = Path(custom)
        return p if p.exists() else None
    candidates = [
        Path("visage.json"),
        Path.home() / ".config" / "visage" / "config.json",
        Path.home() / ".visage.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def load_config(path: str | None = None) -> VisageConfig:
    cfg_path = resolve_config_path(path)
    if cfg_path is None:
        return VisageConfig()

    with open(cfg_path) as f:
        raw: dict[str, Any] = json.load(f)

    defaults = VisageConfig()

    refresh_raw = raw.get("refresh", {})
    refresh_interval = refresh_raw.get("interval", defaults.refresh_interval)

    widgets_raw = raw.get("widgets", {})
    enabled_widgets = widgets_raw.get("enabled", defaults.enabled_widgets)
    widget_order = widgets_raw.get("order", defaults.widget_order)

    # Deep-merge: overriding one key (e.g. thresholds.cpu.red) must not
    # silently drop the other defaults (e.g. thresholds.cpu.yellow).
    user_thresholds = raw.get("thresholds", {})
    if not isinstance(user_thresholds, dict):
        user_thresholds = {}
    thresholds: dict[str, Any] = {}
    for key, default_val in defaults.thresholds.items():
        user_val = user_thresholds.get(key)
        if isinstance(default_val, dict) and isinstance(user_val, dict):
            thresholds[key] = {**default_val, **user_val}
        elif user_val is not None:
            thresholds[key] = user_val
        else:
            thresholds[key] = default_val
    for key, user_val in user_thresholds.items():
        if key not in thresholds:
            thresholds[key] = user_val

    gpu_raw = raw.get("gpu", {})
    gpu_arch_override = gpu_raw.get("arch_override", None)

    alerts = raw.get("alerts", [])

    theme = raw.get("theme", defaults.theme)
    graph_style = raw.get("graph_style", defaults.graph_style)

    return VisageConfig(
        refresh_interval=refresh_interval,
        enabled_widgets=enabled_widgets,
        widget_order=widget_order,
        thresholds=thresholds,
        gpu_arch_override=gpu_arch_override,
        alerts=alerts,
        theme=theme,
        graph_style=graph_style,
    )

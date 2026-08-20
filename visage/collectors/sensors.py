"""Temperature, fan, and power sensor collectors.

Temperature uses psutil.sensors_temperatures().
Fan speed reads hwmon sysfs (/sys/class/hwmon/*/fan*_input).
Power uses RAPL sysfs interface (/sys/class/powercap).
"""

import os
from pathlib import Path
from typing import Any

import psutil


def collect_temperatures() -> dict[str, Any]:
    """Read all available temperature sensors."""
    temps = psutil.sensors_temperatures()
    if not temps:
        return {"available": False, "entries": []}
    entries: list[dict] = []
    for name, sensors in temps.items():
        for sensor in sensors:
            entries.append({
                "label": sensor.label or name,
                "current": sensor.current,
                "high": sensor.high,
                "critical": sensor.critical,
            })
    return {"available": True, "entries": entries}


def collect_fans() -> dict[str, Any]:
    """Read fan speeds from hwmon sysfs."""
    entries: list[dict] = []
    hwmon_base = Path("/sys/class/hwmon")
    if not hwmon_base.exists():
        return {"available": False, "entries": []}

    for hwmon_dir in hwmon_base.iterdir():
        if not hwmon_dir.is_dir():
            continue
        try:
            name = (hwmon_dir / "name").read_text().strip()
        except (OSError, IOError):
            name = "unknown"

        fan_files = sorted(hwmon_dir.glob("fan*_input"))
        for fan_file in fan_files:
            try:
                rpm = int(fan_file.read_text().strip())
                label_file = fan_file.parent / fan_file.name.replace("_input", "_label")
                label = name
                if label_file.exists():
                    try:
                        label = label_file.read_text().strip()
                    except (OSError, IOError):
                        pass
                entries.append({
                    "label": f"{label} {fan_file.stem.replace('_input', '')}",
                    "rpm": rpm,
                })
            except (OSError, ValueError, IOError):
                continue

    return {"available": bool(entries), "entries": entries}


def collect_power() -> dict[str, Any]:
    """Read RAPL power consumption from sysfs."""
    results: list[dict] = []
    base = Path("/sys/class/powercap")
    if not base.exists():
        return {"available": False, "entries": []}
    for rapl_dir in base.glob("intel-rapl*"):
        if not rapl_dir.is_dir():
            continue
        try:
            name = (rapl_dir / "name").read_text().strip()
            energy_uj = int((rapl_dir / "energy_uj").read_text().strip())
            max_uw = int((rapl_dir / "max_energy_range_uj").read_text().strip())
            results.append({
                "name": name,
                "energy_uj": energy_uj,
                "max_energy_uj": max_uw,
            })
        except (OSError, ValueError, IOError):
            continue
    return {"available": bool(results), "entries": results}


def collect() -> dict[str, Any]:
    """Collect all sensor data."""
    return {
        "temperatures": collect_temperatures(),
        "fans": collect_fans(),
        "power": collect_power(),
    }

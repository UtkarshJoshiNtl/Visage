"""Temperature and power sensor collectors.

Temperature uses psutil.sensors_temperatures().
Power uses RAPL sysfs interface (/sys/class/powercap).
"""

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
        "power": collect_power(),
    }

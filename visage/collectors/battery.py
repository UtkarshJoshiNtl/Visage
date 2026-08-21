"""Battery metric collector — reads from sysfs."""

import sys
from pathlib import Path
from typing import Any


def collect() -> dict[str, Any]:
    if sys.platform != "linux":
        return {"available": False, "batteries": [], "percent": 0.0, "status": "Unknown"}

    base = Path("/sys/class/power_supply")
    if not base.exists():
        return {"available": False, "batteries": [], "percent": 0.0, "status": "Unknown"}

    batteries: list[dict[str, Any]] = []
    for bat_dir in sorted(base.glob("BAT*")):
        if not bat_dir.is_dir():
            continue
        try:
            capacity = int((bat_dir / "capacity").read_text().strip())
        except (OSError, ValueError):
            capacity = -1

        try:
            status = (bat_dir / "status").read_text().strip()
        except OSError:
            status = "Unknown"

        energy_now = 0
        energy_full = 0
        power_now = 0

        try:
            energy_now = int((bat_dir / "energy_now").read_text().strip())
        except (OSError, ValueError):
            try:
                charge_now = int((bat_dir / "charge_now").read_text().strip())
                energy_now = charge_now
            except (OSError, ValueError):
                pass

        try:
            energy_full = int((bat_dir / "energy_full").read_text().strip())
        except (OSError, ValueError):
            try:
                charge_full = int((bat_dir / "charge_full").read_text().strip())
                energy_full = charge_full
            except (OSError, ValueError):
                pass

        try:
            power_now = int((bat_dir / "power_now").read_text().strip())
        except (OSError, ValueError):
            try:
                current_now = int((bat_dir / "current_now").read_text().strip())
                voltage = int((bat_dir / "voltage_now").read_text().strip()) / 1_000_000
                power_now = int(current_now * voltage)
            except (OSError, ValueError):
                pass

        batteries.append({
            "name": bat_dir.name,
            "capacity": capacity,
            "status": status,
            "energy_now": energy_now,
            "energy_full": energy_full,
            "power_now": power_now,
        })

    if not batteries:
        return {"available": False, "batteries": [], "percent": 0.0, "status": "Unknown"}

    primary = batteries[0]
    return {
        "available": True,
        "batteries": batteries,
        "percent": primary.get("capacity", 0) if primary.get("capacity", -1) >= 0 else 0.0,
        "status": primary.get("status", "Unknown"),
    }

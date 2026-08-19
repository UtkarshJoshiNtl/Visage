"""PSI (Pressure Stall Information) collector — /proc/pressure/*.

Reads CPU, memory, and I/O pressure metrics from the Linux kernel
(available since Linux 4.20). Reports some/full avg10/avg60/avg300/total.
"""

import sys
from typing import Any

_PSI_PATHS = {
    "cpu": "/proc/pressure/cpu",
    "memory": "/proc/pressure/memory",
    "io": "/proc/pressure/io",
}


def _parse_psi_line(line: str) -> dict[str, float]:
    result = {}
    for token in line.split():
        if "=" in token:
            key, val = token.split("=", 1)
            try:
                result[key] = float(val)
            except ValueError:
                pass
    return result


def _read_psi_file(path: str) -> dict[str, Any]:
    try:
        with open(path) as f:
            lines = f.readlines()
    except (OSError, PermissionError):
        return {}
    result: dict[str, Any] = {}
    for line in lines:
        line = line.strip()
        if line.startswith("some"):
            result["some"] = _parse_psi_line(line)
        elif line.startswith("full"):
            result["full"] = _parse_psi_line(line)
    return result


def collect() -> dict[str, Any]:
    if sys.platform != "linux":
        return {"available": False, "cpu": {}, "memory": {}, "io": {}}

    data: dict[str, Any] = {"available": True}
    for resource, path in _PSI_PATHS.items():
        data[resource] = _read_psi_file(path)
    return data

"""Cache statistics collector.

Reads CPU cache information from /sys/kernel/debug or /proc/cpuinfo.
"""

from pathlib import Path
from typing import Any


def _parse_cpuinfo() -> list[dict[str, str]]:
    """Parse /proc/cpuinfo for cache details."""
    cpus: list[dict[str, str]] = []
    current: dict[str, str] = {}
    try:
        text = Path("/proc/cpuinfo").read_text()
    except (OSError, IOError):
        return []
    for line in text.splitlines():
        if not line.strip():
            if current:
                cpus.append(current)
                current = {}
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            current[key.strip()] = val.strip()
    if current:
        cpus.append(current)
    return cpus


def collect_cpuinfo_cache() -> list[dict[str, Any]]:
    """Extract cache info from /proc/cpuinfo."""
    cpus = _parse_cpuinfo()
    if not cpus:
        return []
    # Index cache sizes by type
    cache_info: dict[str, set[str]] = {}
    for cpu in cpus:
        for key in ("cache size",):
            if key in cpu:
                cache_info.setdefault(key, set()).add(cpu[key])
        for key, val in cpu.items():
            if "cache" in key.lower() and key not in ("cache size", "flags"):
                cache_info.setdefault(key, set()).add(val)
    return [
        {"name": k, "values": sorted(v)} for k, v in cache_info.items()
    ]


def collect_l1d_size() -> str:
    cpus = _parse_cpuinfo()
    if cpus:
        return cpus[0].get("cache size", "unknown")
    return "unknown"


def collect() -> dict[str, Any]:
    """Return cache topology."""
    return {
        "sizes": collect_cpuinfo_cache(),
        "l1d": collect_l1d_size(),
    }

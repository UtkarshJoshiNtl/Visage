"""Memory metric collector — raw /proc/meminfo parser.

Reads only the 4 fields we need (MemTotal, MemAvailable, SwapTotal, SwapFree)
from /proc/meminfo. Opens the file once and rewinds via seek(0) on each tick.
Values are converted from kB to bytes for widget compatibility.
"""

from typing import TextIO

_MEMINFO_PATH = "/proc/meminfo"

_fd: TextIO | None = None


def _get_fd():
    global _fd
    if _fd is None:
        _fd = open(_MEMINFO_PATH)
    return _fd


def _parse_kb(line: str) -> int:
    return int(line.split()[1]) * 1024


def collect() -> dict:
    fd = _get_fd()
    fd.seek(0)

    mem_total = 0
    mem_avail = 0
    swap_total = 0
    swap_free = 0

    for line in fd:
        if line.startswith("MemTotal:"):
            mem_total = _parse_kb(line)
        elif line.startswith("MemAvailable:"):
            mem_avail = _parse_kb(line)
        elif line.startswith("SwapTotal:"):
            swap_total = _parse_kb(line)
        elif line.startswith("SwapFree:"):
            swap_free = _parse_kb(line)

    mem_used = mem_total - mem_avail
    swap_used = swap_total - swap_free
    mem_pct = (mem_used / mem_total * 100.0) if mem_total > 0 else 0.0

    return {
        "total": mem_total,
        "available": mem_avail,
        "used": mem_used,
        "percent": mem_pct,
        "swap_total": swap_total,
        "swap_used": swap_used,
        "swap_percent": (swap_used / swap_total * 100.0) if swap_total > 0 else 0.0,
    }

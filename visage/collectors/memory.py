"""Memory metric collector — raw /proc/meminfo parser with detailed breakdown."""

import sys
import threading
from typing import TextIO

_MEMINFO_PATH = "/proc/meminfo"

_lock = threading.Lock()
_fd: TextIO | None = None


def _get_fd():
    global _fd
    if sys.platform != "linux":
        return None
    if _fd is not None:
        try:
            _fd.seek(0)
            return _fd
        except (OSError, ValueError):
            try:
                _fd.close()
            except OSError:
                pass
            _fd = None
    try:
        _fd = open(_MEMINFO_PATH)
    except OSError:
        return None
    return _fd


def _parse_kb(line: str) -> int:
    return int(line.split()[1]) * 1024


def collect() -> dict:
    with _lock:
        fd = _get_fd()
        if fd is None:
            return {
                "total": 0,
                "available": 0,
                "used": 0,
                "percent": 0.0,
                "swap_total": 0,
                "swap_used": 0,
                "swap_percent": 0.0,
                "buffers": 0,
                "cached": 0,
                "sreclaimable": 0,
                "dirty": 0,
            }
        fd.seek(0)

        mem_total = 0
        mem_avail = 0
        swap_total = 0
        swap_free = 0
        buffers = 0
        cached = 0
        sreclaimable = 0
        dirty = 0

        for line in fd:
            if line.startswith("MemTotal:"):
                mem_total = _parse_kb(line)
            elif line.startswith("MemAvailable:"):
                mem_avail = _parse_kb(line)
            elif line.startswith("SwapTotal:"):
                swap_total = _parse_kb(line)
            elif line.startswith("SwapFree:"):
                swap_free = _parse_kb(line)
            elif line.startswith("Buffers:"):
                buffers = _parse_kb(line)
            elif line.startswith("Cached:"):
                cached = _parse_kb(line)
            elif line.startswith("SReclaimable:"):
                sreclaimable = _parse_kb(line)
            elif line.startswith("Dirty:"):
                dirty = _parse_kb(line)

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
            "buffers": buffers,
            "cached": cached,
            "sreclaimable": sreclaimable,
            "dirty": dirty,
        }

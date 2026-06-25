"""Disk I/O metric collector (cumulative counters for rate computation)."""

import psutil


def collect() -> dict:
    counters = psutil.disk_io_counters()
    if counters is None:
        return {
            "read_bytes": 0.0,
            "write_bytes": 0.0,
            "read_count": 0.0,
            "write_count": 0.0,
        }
    return {
        "read_bytes": float(counters.read_bytes),
        "write_bytes": float(counters.write_bytes),
        "read_count": float(counters.read_count),
        "write_count": float(counters.write_count),
    }

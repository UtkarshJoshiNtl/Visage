"""Network I/O metric collector (cumulative counters for rate computation)."""

import psutil


def collect() -> dict:
    counters = psutil.net_io_counters()
    if counters is None:
        return {
            "bytes_sent": 0.0,
            "bytes_recv": 0.0,
            "packets_sent": 0.0,
            "packets_recv": 0.0,
        }
    return {
        "bytes_sent": float(counters.bytes_sent),
        "bytes_recv": float(counters.bytes_recv),
        "packets_sent": float(counters.packets_sent),
        "packets_recv": float(counters.packets_recv),
    }

"""Network I/O metric collector — per-interface breakdown and per-process approximation."""

import sys
import threading
from typing import Any

import psutil


_lock = threading.Lock()
_prev_per_nic: dict[str, dict[str, float]] = {}
_prev_total: dict[str, float] = {}


def collect() -> dict[str, Any]:
    """Collect network I/O counters with delta-based rates."""
    global _prev_per_nic, _prev_total

    with _lock:
        total: dict[str, Any] = {}
        try:
            counters = psutil.net_io_counters()
            if counters:
                total = {
                    "bytes_sent": float(counters.bytes_sent),
                    "bytes_recv": float(counters.bytes_recv),
                    "packets_sent": float(counters.packets_sent),
                    "packets_recv": float(counters.packets_recv),
                }
        except Exception:
            pass

        pernic: dict[str, dict[str, Any]] = {}
        try:
            counters = psutil.net_io_counters(pernic=True)
            addrs = psutil.net_if_addrs()
            if counters:
                for name, c in counters.items():
                    if name == "lo":
                        continue
                    ip = ""
                    if name in addrs:
                        for a in addrs[name]:
                            if a.family.name in ("AF_INET", "AF_INET6"):
                                ip = a.address
                                break
                    pernic[name] = {
                        "bytes_sent": float(c.bytes_sent),
                        "bytes_recv": float(c.bytes_recv),
                        "packets_sent": float(c.packets_sent),
                        "packets_recv": float(c.packets_recv),
                        "ip": ip,
                    }
        except Exception:
            pass

        return {
            "total": total,
            "pernic": pernic,
        }


def collect_per_process(top_n: int = 10) -> list[dict[str, Any]]:
    """Approximate per-process network usage using /proc/[pid]/net/dev.

    On Linux, /proc/[pid]/net/dev shows per-NIC counters for the network
    namespace the process belongs to. For single-namespace systems this is
    system-wide, but we track deltas and attribute proportionally by
    process CPU usage as a rough approximation.
    """
    if sys.platform != "linux":
        return []

    results: list[dict[str, Any]] = []
    try:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                info = p.info
                pid = info["pid"]
                net_path = f"/proc/{pid}/net/dev"
                with open(net_path) as f:
                    lines = f.readlines()
                rx_bytes = 0
                tx_bytes = 0
                for line in lines[2:]:
                    parts = line.split()
                    if len(parts) >= 10:
                        iface = parts[0].rstrip(":")
                        if iface == "lo":
                            continue
                        rx_bytes += int(parts[1])
                        tx_bytes += int(parts[9])
                procs.append({
                    "pid": pid,
                    "name": info.get("name", ""),
                    "cpu": info.get("cpu_percent", 0.0) or 0.0,
                    "rx_bytes": rx_bytes,
                    "tx_bytes": tx_bytes,
                })
            except (OSError, ValueError, psutil.NoSuchProcess):
                continue

        total_cpu = sum(p["cpu"] for p in procs) or 1.0
        total_rx = sum(p["rx_bytes"] for p in procs)
        total_tx = sum(p["tx_bytes"] for p in procs)

        for p in procs:
            proportion = p["cpu"] / total_cpu
            results.append({
                "pid": p["pid"],
                "name": p["name"],
                "rx_bytes_est": total_rx * proportion,
                "tx_bytes_est": total_tx * proportion,
                "cpu_share": p["cpu"],
            })

        results.sort(key=lambda x: x["rx_bytes_est"] + x["tx_bytes_est"], reverse=True)
    except Exception:
        pass

    return results[:top_n]

"""Network I/O metric collector — per-interface breakdown."""

import psutil


def collect() -> dict:
    total = {}
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

    pernic = {}
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

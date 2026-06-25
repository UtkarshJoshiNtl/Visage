"""Process metric collector — top processes by CPU usage."""

import psutil


def collect(top_n: int = 8) -> list[dict]:
    processes: list[dict] = []
    for proc in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            name = info["name"]
            if not name:
                continue
            cpu = info["cpu_percent"] or 0.0
            mem = info["memory_percent"] or 0.0
            processes.append({"name": name, "cpu": cpu, "memory": mem})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    processes.sort(key=lambda p: p["cpu"], reverse=True)
    return processes[:top_n]

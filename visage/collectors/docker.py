"""Docker container collector — parses docker stats output (zero deps)."""

import json
import subprocess
import sys
from typing import Any


def _run_docker_stats() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            [
                "docker", "stats", "--no-stream",
                "--format", '{"name":"{{.Name}}","cpu":"{{.CPUPerc}}",'
                '"mem_usage":"{{.MemUsage}}","mem_pct":"{{.MemPerc}}",'
                '"net_io":"{{.NetIO}}","block_io":"{{.BlockIO}}",'
                '"pids":"{{.PIDs}}"}',
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []
        containers = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                containers.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return containers
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def _parse_rate(s: str) -> float:
    s = s.strip()
    parts = s.split("/")
    if len(parts) == 2:
        s = parts[0].strip()
    multipliers = {
        "B": 1, "KiB": 1024, "MiB": 1048576, "GiB": 1073741824,
        "KB": 1000, "MB": 1000000, "GB": 1000000000,
    }
    for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
        if s.endswith(suffix):
            try:
                return float(s[: -len(suffix)].strip()) * mult
            except ValueError:
                return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def collect() -> dict[str, Any]:
    if sys.platform != "linux" and sys.platform != "darwin":
        return {"available": False, "containers": []}

    raw = _run_docker_stats()
    if not raw:
        return {"available": False, "containers": []}

    containers = []
    for c in raw:
        cpu_str = c.get("cpu", "0%").replace("%", "")
        mem_pct_str = c.get("mem_pct", "0%").replace("%", "")
        try:
            cpu_pct = float(cpu_str)
        except ValueError:
            cpu_pct = 0.0
        try:
            mem_pct = float(mem_pct_str)
        except ValueError:
            mem_pct = 0.0

        containers.append({
            "name": c.get("name", "?"),
            "cpu_pct": cpu_pct,
            "mem_pct": mem_pct,
            "mem_usage": c.get("mem_usage", ""),
            "net_io": c.get("net_io", ""),
            "block_io": c.get("block_io", ""),
            "pids": c.get("pids", "0"),
        })

    return {"available": True, "containers": containers}

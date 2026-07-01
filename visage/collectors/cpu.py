"""CPU metric collector — raw /proc/stat parser.

Parses jiffie counters directly from the kernel's virtual filesystem,
eliminating the psutil dependency. Opens /proc/stat once at module init
and rewinds via seek(0) on each tick to avoid open/close overhead.
"""

import sys
from typing import TextIO

_STAT_PATH = "/proc/stat"
_CPUFREQ_BASE = "/sys/devices/system/cpu"

_fd: TextIO | None = None
_cpu_count: int = 0
_prev: dict[str, tuple[int, int]] = {}


def _get_fd():
    global _fd
    if _fd is None:
        if sys.platform != "linux":
            return None
        try:
            _fd = open(_STAT_PATH)
        except OSError:
            return None
    return _fd


def _parse_jiffies(line: str) -> tuple[int, int]:
    parts = line.split()
    fields = [int(p) for p in parts[1:]]
    total = sum(fields)
    idle = fields[3] + fields[4]
    return total, idle


def _read_cpufreq() -> float:
    try:
        with open(f"{_CPUFREQ_BASE}/cpu0/cpufreq/scaling_cur_freq") as f:
            return float(f.read().strip()) / 1000.0
    except (OSError, FileNotFoundError, ValueError):
        return 0.0


def collect() -> dict:
    global _cpu_count, _prev

    fd = _get_fd()
    if fd is None:
        return {
            "percent": 0.0,
            "per_cpu": [],
            "count": 0,
            "freq_current": 0.0,
            "freq_min": 0.0,
            "freq_max": 0.0,
            "ctx_switches": 0,
            "interrupts": 0,
            "soft_interrupts": 0,
            "syscalls": 0,
        }
    fd.seek(0)

    aggregate_total = 0
    aggregate_idle = 0
    cores: list[tuple[int, int]] = []
    ctx = 0
    intr = 0
    softirq = 0
    procs = 0

    for line in fd:
        if line.startswith("cpu "):
            aggregate_total, aggregate_idle = _parse_jiffies(line)
        elif line.startswith("cpu") and line[3].isdigit():
            cores.append(_parse_jiffies(line))
        elif line.startswith("ctxt "):
            ctx = int(line.split()[1])
        elif line.startswith("intr "):
            intr = int(line.split()[1])
        elif line.startswith("softirq "):
            softirq = int(line.split()[1])
        elif line.startswith("processes "):
            procs = int(line.split()[1])

    _cpu_count = len(cores)

    percent = 0.0
    if "cpu" in _prev:
        pt, pi = _prev["cpu"]
        dt = aggregate_total - pt
        di = aggregate_idle - pi
        if dt > 0:
            percent = (1.0 - di / dt) * 100.0
    _prev["cpu"] = (aggregate_total, aggregate_idle)

    per_cpu: list[float] = []
    for i, (total, idle) in enumerate(cores):
        key = f"cpu{i}"
        pct = 0.0
        if key in _prev:
            pt, pi = _prev[key]
            dt = total - pt
            di = idle - pi
            if dt > 0:
                pct = (1.0 - di / dt) * 100.0
        _prev[key] = (total, idle)
        per_cpu.append(max(0.0, min(pct, 100.0)))

    freq = _read_cpufreq()

    return {
        "percent": max(0.0, min(percent, 100.0)),
        "per_cpu": per_cpu,
        "count": _cpu_count,
        "freq_current": freq,
        "freq_min": 0.0,
        "freq_max": 0.0,
        "ctx_switches": ctx,
        "interrupts": intr,
        "soft_interrupts": softirq,
        "syscalls": procs,
    }

"""CPU metric collector — raw /proc/stat parser.

Parses jiffie counters directly from the kernel's virtual filesystem,
eliminating the psutil dependency. Opens /proc/stat once at module init
and rewinds via seek(0) on each tick to avoid open/close overhead.
"""

import os
import sys
import threading
import time
from pathlib import Path
from typing import TextIO

_STAT_PATH = "/proc/stat"
_UPTIME_PATH = "/proc/uptime"
_CPUFREQ_BASE = "/sys/devices/system/cpu"
_CPUINFO_PATH = "/proc/cpuinfo"

_lock = threading.Lock()
_fd: TextIO | None = None
_cpu_count: int = 0
_prev: dict[str, tuple[int, int]] = {}
_prev_ctx: int = 0
_prev_intr: int = 0
_prev_softirq: int = 0
_prev_time: float = 0.0
_model_name: str = ""
_model_found: bool = False


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


def _read_cpufreq() -> tuple[float, float, float]:
    cur = 0.0
    mn = 0.0
    mx = 0.0
    try:
        entries = sorted(Path(_CPUFREQ_BASE).glob("cpu*/cpufreq/scaling_cur_freq"))
        if entries:
            vals = []
            for e in entries:
                try:
                    vals.append(float(e.read_text().strip()) / 1000.0)
                except (OSError, ValueError):
                    continue
            if vals:
                cur = sum(vals) / len(vals)
    except (OSError, FileNotFoundError):
        pass
    try:
        policy = Path(_CPUFREQ_BASE) / "cpufreq" / "policy0"
        mn = float((policy / "scaling_min_freq").read_text().strip()) / 1000.0
    except (OSError, FileNotFoundError, ValueError):
        pass
    try:
        policy = Path(_CPUFREQ_BASE) / "cpufreq" / "policy0"
        mx = float((policy / "scaling_max_freq").read_text().strip()) / 1000.0
    except (OSError, FileNotFoundError, ValueError):
        pass
    return cur, mn, mx


def _read_per_core_cpufreq() -> list[float]:
    freqs: list[float] = []
    try:
        entries = sorted(Path(_CPUFREQ_BASE).glob("cpu*/cpufreq/scaling_cur_freq"))
        for e in entries:
            try:
                freqs.append(float(e.read_text().strip()) / 1000.0)
            except (OSError, ValueError):
                freqs.append(0.0)
    except (OSError, FileNotFoundError):
        pass
    return freqs


def _read_model_name() -> str:
    global _model_name, _model_found
    if _model_found:
        return _model_name
    _model_found = True
    try:
        with open(_CPUINFO_PATH) as f:
            for line in f:
                if line.startswith("model name"):
                    _model_name = line.split(":", 1)[1].strip()
                    return _model_name
    except OSError:
        pass
    return ""


def _read_uptime() -> float:
    try:
        with open(_UPTIME_PATH) as f:
            return float(f.read().split()[0])
    except (OSError, ValueError):
        return 0.0


def collect() -> dict:
    global _cpu_count, _prev, _prev_ctx, _prev_intr, _prev_softirq, _prev_time

    with _lock:
        fd = _get_fd()
        now = time.monotonic()

        model = _read_model_name()
        uptime = _read_uptime()

        if fd is None:
            return {
                "percent": 0.0,
                "per_cpu": [],
                "count": 0,
                "freq_current": 0.0,
                "freq_min": 0.0,
                "freq_max": 0.0,
                "per_core_freq": [],
                "ctx_switches": 0,
                "ctx_per_sec": 0.0,
                "interrupts": 0,
                "interrupts_per_sec": 0.0,
                "soft_interrupts": 0,
                "soft_per_sec": 0.0,
                "syscalls": 0,
                "model": model,
                "uptime": uptime,
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

        dt_wall = now - _prev_time if _prev_time > 0 else 0.0

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

        ctx_per_sec = 0.0
        intr_per_sec = 0.0
        soft_per_sec = 0.0
        if dt_wall > 0 and _prev_time > 0:
            ctx_per_sec = max(0.0, (ctx - _prev_ctx) / dt_wall)
            intr_per_sec = max(0.0, (intr - _prev_intr) / dt_wall)
            soft_per_sec = max(0.0, (softirq - _prev_softirq) / dt_wall)
        _prev_ctx = ctx
        _prev_intr = intr
        _prev_softirq = softirq
        _prev_time = now

        freq_cur, freq_min, freq_max = _read_cpufreq()
        per_core_freq = _read_per_core_cpufreq()

        return {
            "percent": max(0.0, min(percent, 100.0)),
            "per_cpu": per_cpu,
            "count": _cpu_count,
            "freq_current": freq_cur,
            "freq_min": freq_min,
            "freq_max": freq_max,
            "per_core_freq": per_core_freq,
            "ctx_switches": ctx,
            "ctx_per_sec": ctx_per_sec,
            "interrupts": intr,
            "interrupts_per_sec": intr_per_sec,
            "soft_interrupts": softirq,
            "soft_per_sec": soft_per_sec,
            "syscalls": procs,
            "model": model,
            "uptime": uptime,
        }

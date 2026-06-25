"""CPU metric collector."""

import psutil


def collect() -> dict:
    usage = psutil.cpu_percent(interval=0)
    per_cpu = psutil.cpu_percent(interval=0, percpu=True)
    freq = psutil.cpu_freq()
    stats = psutil.cpu_stats()
    return {
        "percent": usage,
        "per_cpu": per_cpu,
        "count": psutil.cpu_count(),
        "freq_current": freq.current if freq else 0.0,
        "freq_min": freq.min if freq and freq.min else 0.0,
        "freq_max": freq.max if freq and freq.max else 0.0,
        "ctx_switches": stats.ctx_switches,
        "interrupts": stats.interrupts,
        "soft_interrupts": stats.soft_interrupts,
        "syscalls": stats.syscalls,
    }

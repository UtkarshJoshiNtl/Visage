"""Hardware-isolated benchmark runner.

Usage::

    from visage.runners.isolated import run_isolated

    result = run_isolated("/usr/bin/sort", ["/tmp/large.txt"], core_id=3)
    print(f"IPC: {result.ipc:.3f}, wall: {result.wall_time:.3f}s")
"""

from visage.runners.isolated import (
    BenchmarkResult,
    CpuCage,
    CpuFreqUnavailableError,
    run_isolated,
)

__all__ = ["BenchmarkResult", "CpuCage", "CpuFreqUnavailableError", "run_isolated"]

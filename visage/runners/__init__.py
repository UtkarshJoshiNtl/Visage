"""Hardware-isolated benchmark runner.

Usage::

    from visage.runners import run_isolated, run_benchmark

    # single run
    result = run_isolated("/usr/bin/sort", ["/tmp/large.txt"], core_id=3)
    print(f"IPC: {result.ipc:.3f}, wall: {result.wall_time:.3f}s")

    # repeated runs with noise filtering
    summary = run_benchmark("/usr/bin/sort", ["/tmp/large.txt"],
                            core_id=3, iterations=10)
    print(f"IPC: μ={summary.ipc_mean:.3f} σ={summary.ipc_std:.3f} "
          f"noisy={summary.noisy}")
"""

from visage.runners.ci import (
    CiGateConfig,
    CiGateResult,
    generate_markdown_report,
    run_ci_gate,
)
from visage.runners.isolated import (
    BenchmarkResult,
    BenchmarkSummary,
    CpuCage,
    CpuFreqUnavailableError,
    run_benchmark,
    run_isolated,
)

__all__ = [
    "BenchmarkResult",
    "BenchmarkSummary",
    "CiGateConfig",
    "CiGateResult",
    "CpuCage",
    "CpuFreqUnavailableError",
    "generate_markdown_report",
    "run_benchmark",
    "run_ci_gate",
    "run_isolated",
]

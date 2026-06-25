"""Benchmark runner — CPU, memory, and disk performance tests."""

import math
import os
import tempfile
import time
from typing import Any

from visage.util import format_bytes, format_rate


class BenchmarkRunner:
    """Run performance benchmarks and return scored results."""

    def cpu(self, duration: float = 5.0) -> dict[str, Any]:
        """CPU benchmark — compute pi via Leibniz series."""
        start = time.monotonic()
        end = start + duration
        iterations = 0
        pi_approx = 0.0
        sign = 1
        while time.monotonic() < end:
            pi_approx += sign / (2 * iterations + 1)
            sign = -sign
            iterations += 1
        pi_approx *= 4
        ops_per_sec = iterations / duration
        return {
            "test": "cpu_pi",
            "iterations": iterations,
            "duration": duration,
            "ops_per_sec": ops_per_sec,
            "pi_approx": pi_approx,
            "score": int(ops_per_sec / 1000),
        }

    def memory(self, mb: int = 256) -> dict[str, Any]:
        """Memory bandwidth benchmark — sequential read/write."""
        size = mb * 1024 * 1024
        arr = bytearray(size)
        start = time.monotonic()
        for i in range(len(arr)):
            arr[i] = (i * 7) & 0xFF
        write_time = time.monotonic() - start
        start = time.monotonic()
        total = 0
        for val in arr:
            total += val
        read_time = time.monotonic() - start
        _ = total
        write_bw = size / write_time
        read_bw = size / read_time
        return {
            "test": "memory_bandwidth",
            "size": size,
            "write_bandwidth": write_bw,
            "read_bandwidth": read_bw,
            "write_time": write_time,
            "read_time": read_time,
            "score": int((write_bw + read_bw) / 2 / 1_000_000),
        }

    def disk(self, mb: int = 128) -> dict[str, Any]:
        """Disk benchmark — sequential write/read on a temp file."""
        size = mb * 1024 * 1024
        data = os.urandom(size)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmppath = f.name
            start = time.monotonic()
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
            write_time = time.monotonic() - start
            start = time.monotonic()
            f.seek(0)
            _ = f.read(size)
            read_time = time.monotonic() - start
        os.unlink(tmppath)
        write_bw = size / write_time if write_time else 0
        read_bw = size / read_time if read_time else 0
        return {
            "test": "disk_sequential",
            "size": size,
            "write_bandwidth": write_bw,
            "read_bandwidth": read_bw,
            "write_time": write_time,
            "read_time": read_time,
            "score": int((write_bw + read_bw) / 2 / 1_000_000),
        }

    def run_all(self) -> dict[str, Any]:
        """Run all benchmarks and return results."""
        return {
            "cpu": self.cpu(),
            "memory": self.memory(),
            "disk": self.disk(),
        }

    def summary(self, results: dict[str, Any]) -> str:
        lines = []
        for name, res in results.items():
            score = res.get("score", 0)
            lines.append(f"[bold]{name.upper()}[/]  score: {score}")
            if "ops_per_sec" in res:
                lines.append(f"  {res['ops_per_sec']:.0f} ops/s")
            if "write_bandwidth" in res:
                w = format_rate(res["write_bandwidth"])
                r = format_rate(res["read_bandwidth"])
                lines.append(f"  Write: {w}  Read: {r}")
        return "\n".join(lines)

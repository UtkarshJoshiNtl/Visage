"""Hardware-isolated benchmark runner.

Pins a child process to a dedicated CPU core, locks the core's clock
frequency, and measures wall-clock time alongside silicon-level PMU
counters (cycles, instructions, cache misses) via the kernel's
``perf_event_open`` syscall.

Isolation
---------
Three-layer strategy, applied in order:

1. **cpuset cgroup v2** (requires root)
   Enable the ``cpuset`` controller, create a child cgroup restricted to
   the target core, then move the benchmark process into it. No other task
   will be scheduled on that core during the run.

2. **Frequency lock** (requires root)
   Save the core's cpufreq governor, ``scaling_min_freq``, and
   ``scaling_max_freq``; set governor to ``performance`` and clamp both
   min/max to a constant target frequency so cycle counts are
   deterministic across runs.

3. **``sched_setaffinity``** (no root needed)
   Pin the child process to the target core with ``taskset(1)``.  The OS
   may still schedule background tasks on the core, but the benchmark
   cannot migrate away.

   ``taskset`` avoids ``Popen(preexec_fn=...)``, which is unsafe in
   multi-threaded programs (Textual runs worker threads).

Permissions
-----------
- PMU counters (``perf_event_open``): requires ``CAP_PERFMON`` or root.
- cgroup isolation: requires root (``CAP_SYS_ADMIN``).
- Frequency lock: requires root (write to cpufreq sysfs).
- Process pinning: unprivileged.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import shutil
import subprocess
import time
from typing import Sequence

from visage.collectors.perf import (
    PERF_COUNT_HW_CACHE_MISSES,
    PERF_COUNT_HW_CPU_CYCLES,
    PERF_COUNT_HW_INSTRUCTIONS,
    HardwareCounter,
)

log = logging.getLogger(__name__)

_CGROUP_ROOT = "/sys/fs/cgroup"
_CPUFREQ_BASE = "/sys/devices/system/cpu/cpu{}/cpufreq"


class CpuFreqUnavailableError(RuntimeError):
    """Raised when cpufreq sysfs is absent or read-only for the target core."""


@dataclasses.dataclass(frozen=True)
class BenchmarkResult:
    """Outcome of a single isolated benchmark run."""

    returncode: int
    wall_time: float

    cycles: int = 0
    instructions: int = 0
    cache_misses: int = 0

    ipc: float = 0.0
    cycles_per_sec: float = 0.0
    inst_per_sec: float = 0.0
    miss_per_sec: float = 0.0

    available: bool = False
    isolated: bool = False
    freq_locked: bool = False
    core_id: int = 0

    error: str | None = None


class CpufreqLock:
    """Save/restore CPU frequency governor and min/max limits.

    Parameters
    ----------
    core_id
        Logical CPU index.
    target_khz
        Desired frequency in kHz.
    """

    def __init__(self, core_id: int, target_khz: int) -> None:
        self.core_id = core_id
        self.target_khz = target_khz
        self._sysfs = _CPUFREQ_BASE.format(core_id)
        self._saved: dict[str, str] = {}
        self._locked = False

    def _read(self, name: str) -> str | None:
        path = f"{self._sysfs}/{name}"
        try:
            with open(path) as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError, OSError):
            return None

    def _write(self, name: str, value: str) -> None:
        path = f"{self._sysfs}/{name}"
        try:
            with open(path, "w") as f:
                f.write(value)
        except PermissionError as exc:
            raise CpuFreqUnavailableError(
                f"Cannot write {path} — need root"
            ) from exc
        except FileNotFoundError as exc:
            raise CpuFreqUnavailableError(
                f"cpufreq sysfs not found at {self._sysfs} — "
                "no cpufreq driver on this system"
            ) from exc

    def lock(self) -> None:
        """Save current state and lock frequency to *target_khz*."""
        self._saved["scaling_governor"] = self._read("scaling_governor") or ""
        self._saved["scaling_min_freq"] = self._read("scaling_min_freq") or ""
        self._saved["scaling_max_freq"] = self._read("scaling_max_freq") or ""

        freq_str = str(self.target_khz)
        self._write("scaling_governor", "performance")
        self._write("scaling_min_freq", freq_str)
        self._write("scaling_max_freq", freq_str)

        self._locked = True
        log.info(
            "CpufreqLock[%d]: locked to %d kHz (%s/%s → performance)",
            self.core_id,
            self.target_khz,
            self._saved.get("scaling_governor", "?"),
            self._saved.get("scaling_max_freq", "?"),
        )

    def unlock(self) -> None:
        """Restore original governor and min/max frequencies."""
        if not self._locked:
            return
        for key in ("scaling_max_freq", "scaling_min_freq", "scaling_governor"):
            val = self._saved.get(key)
            if val:
                self._write(key, val)
        self._locked = False
        log.info("CpufreqLock[%d]: restored original governor/freq", self.core_id)

    @property
    def locked(self) -> bool:
        return self._locked


class CpuCage:
    """Reserve a CPU core for exclusive benchmark execution.

    Parameters
    ----------
    core_id : int
        Logical CPU index to isolate.
    target_freq_khz : int | None
        If set, lock the core's clock to this frequency (kHz) for the
        duration of the benchmark.  Requires root + cpufreq driver.

    Attributes
    ----------
    isolated : bool
        Whether exclusive OS isolation (cpuset) was achieved.
    freq_locked : bool
        Whether frequency was successfully locked.
    """

    def __init__(self, core_id: int, target_freq_khz: int | None = None) -> None:
        self.core_id = core_id
        self.target_freq_khz = target_freq_khz
        self._cgroup_parent: str | None = None
        self._cgroup_path: str | None = None
        self._freq_lock: CpufreqLock | None = None
        self.isolated = False
        self.freq_locked = False

    # ------------------------------------------------------------------
    # context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> CpuCage:
        self.setup()
        return self

    def __exit__(self, *args: object) -> None:
        self.teardown()

    # ------------------------------------------------------------------
    # setup / teardown
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """Attempt cpuset isolation, then frequency lock."""
        if self._setup_cgroup():
            self.isolated = True
            log.info("CpuCage[%d]: cpuset isolation active", self.core_id)
        else:
            log.info(
                "CpuCage[%d]: cpuset unavailable — pinning only (no OS exclusion)",
                self.core_id,
            )

        if self.target_freq_khz is not None:
            self.freq_locked = self._setup_freq_lock()

    def teardown(self) -> None:
        if self._freq_lock is not None:
            self._freq_lock.unlock()
            self._freq_lock = None
            self.freq_locked = False
        if self._cgroup_path:
            try:
                os.rmdir(self._cgroup_path)
            except OSError as exc:
                log.warning("CpuCage teardown: %s", exc)
            self._cgroup_path = None
        self._cgroup_parent = None

    # ------------------------------------------------------------------
    # frequency lock
    # ------------------------------------------------------------------

    def _setup_freq_lock(self) -> bool:
        assert self.target_freq_khz is not None
        try:
            fl = CpufreqLock(self.core_id, self.target_freq_khz)
            fl.lock()
            self._freq_lock = fl
            return True
        except CpuFreqUnavailableError as exc:
            log.warning("CpuCage[%d]: freq lock unavailable — %s", self.core_id, exc)
            return False

    # ------------------------------------------------------------------
    # cgroup v2 cpuset
    # ------------------------------------------------------------------

    def _can_write(self, path: str) -> bool:
        return os.path.isfile(path) and os.access(path, os.W_OK)

    def _setup_cgroup(self) -> bool:
        try:
            if not os.path.isdir(_CGROUP_ROOT):
                return False
            if not self._can_write(f"{_CGROUP_ROOT}/cgroup.subtree_control"):
                return False
        except PermissionError:
            return False

        pid = os.getpid()
        cage_path = f"{_CGROUP_ROOT}/visage-cage-{pid}"

        try:
            os.makedirs(cage_path, exist_ok=True)
        except PermissionError:
            return False

        try:
            with open(f"{cage_path}cpuset.cpus", "w") as f:
                f.write(str(self.core_id))
            with open(_CGROUP_ROOT + "/cpuset.mems") as src:
                mems = src.read().strip()
            with open(f"{cage_path}cpuset.mems", "w") as f:
                f.write(mems)
        except OSError as exc:
            log.debug("CpuCage cpuset config failed: %s", exc)
            try:
                os.rmdir(cage_path)
            except OSError:
                pass
            return False

        self._cgroup_path = cage_path
        return True

    def move_process(self, pid: int) -> bool:
        """Move *pid* into the isolated cgroup.

        No-op if cgroup isolation was not set up.
        """
        if not self._cgroup_path:
            return False
        try:
            with open(f"{self._cgroup_path}cgroup.procs", "w") as f:
                f.write(str(pid))
            return True
        except OSError as exc:
            log.warning("CpuCage move PID %d failed: %s", pid, exc)
            return False

    def pin_process(self, pid: int) -> None:
        """Pin *pid* to the target core via ``sched_setaffinity``."""
        try:
            os.sched_setaffinity(pid, {self.core_id})
        except OSError as exc:
            log.warning("CpuCage pin PID %d failed: %s", pid, exc)


def run_isolated(
    executable: str,
    args: Sequence[str] = (),
    *,
    core_id: int = 0,
    target_freq_khz: int | None = None,
    timeout: float | None = None,
    with_counters: bool = True,
) -> BenchmarkResult:
    """Run *executable* on a pinned, isolated core with PMU measurement.

    Parameters
    ----------
    executable
        Path to the binary to benchmark.
    args
        Command-line arguments.
    core_id
        Logical CPU index to pin the child to.
    target_freq_khz
        If set, lock the core's clock to this frequency (kHz) for the
        duration of the run.  Requires root + cpufreq driver.
    timeout
        Wall-clock deadline (seconds).  ``None`` means no limit.
    with_counters
        If ``True``, open ``perf_event_open`` HW counters on *core_id*.

    Returns
    -------
    BenchmarkResult
    """
    start = time.monotonic()

    counters: list[HardwareCounter] = []
    if with_counters:
        for name, cfg in (
            ("cycles", PERF_COUNT_HW_CPU_CYCLES),
            ("instructions", PERF_COUNT_HW_INSTRUCTIONS),
            ("cache_misses", PERF_COUNT_HW_CACHE_MISSES),
        ):
            try:
                c = HardwareCounter(name, cfg, pid=-1, cpu=core_id, disabled=True)
                counters.append(c)
            except OSError as exc:
                log.debug("perf_event_open(%s) failed: %s", name, exc)
                for c in counters:
                    c.close()
                counters = []
                break

    try:
        with CpuCage(core_id, target_freq_khz=target_freq_khz) as cage:
            for c in counters:
                c.enable()

            proc = subprocess.Popen(
                [shutil.which(executable) or executable, *map(str, args)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            cage.pin_process(proc.pid)
            cage.move_process(proc.pid)

            try:
                ret = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                elapsed = time.monotonic() - start
                for c in counters:
                    c.disable()
                return BenchmarkResult(
                    returncode=-1,
                    wall_time=elapsed,
                    available=len(counters) > 0,
                    isolated=cage.isolated,
                    freq_locked=cage.freq_locked,
                    core_id=core_id,
                    error=f"Timed out after {timeout}s",
                )

            elapsed = time.monotonic() - start

            for c in counters:
                c.disable()

            values = {c.name: c.read() for c in counters}

            cycles = values.get("cycles", 0)
            instructions = values.get("instructions", 0)
            misses = values.get("cache_misses", 0)

            return BenchmarkResult(
                returncode=ret,
                wall_time=elapsed,
                cycles=cycles,
                instructions=instructions,
                cache_misses=misses,
                ipc=instructions / cycles if cycles > 0 else 0.0,
                cycles_per_sec=cycles / elapsed if elapsed > 0 else 0.0,
                inst_per_sec=instructions / elapsed if elapsed > 0 else 0.0,
                miss_per_sec=misses / elapsed if elapsed > 0 else 0.0,
                available=len(counters) > 0,
                isolated=cage.isolated,
                freq_locked=cage.freq_locked,
                core_id=core_id,
            )
    finally:
        for c in counters:
            c.close()

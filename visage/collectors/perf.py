"""Hardware PMU counters via perf_event_open.

Reads CPU cycles, instructions, and last-level cache misses directly from
the silicon's Performance Monitoring Unit using the kernel's perf_event_open
syscall. No third-party dependencies — uses raw ctypes.

Requires root / CAP_PERFMON / CAP_SYS_ADMIN (perf_event_paranoid <= 0).
Falls back to returning zeros if the syscall is not permitted.
"""

import ctypes
import fcntl
import os
import struct
import time
from typing import Any

__NR_perf_event_open = 298

PERF_TYPE_HARDWARE = 0

PERF_COUNT_HW_CPU_CYCLES = 0
PERF_COUNT_HW_INSTRUCTIONS = 1
PERF_COUNT_HW_CACHE_REFERENCES = 2
PERF_COUNT_HW_CACHE_MISSES = 3

PERF_EVENT_IOC_ENABLE = 0x2400
PERF_EVENT_IOC_DISABLE = 0x2401
PERF_EVENT_IOC_RESET = 0x2403

_libc = ctypes.CDLL("libc.so.6", use_errno=True)


class _PerfEventAttr(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("size", ctypes.c_uint32),
        ("config", ctypes.c_uint64),
        ("sample_period", ctypes.c_uint64),
        ("sample_type", ctypes.c_uint64),
        ("read_format", ctypes.c_uint64),
        ("flags", ctypes.c_uint64),
        ("wakeup_events", ctypes.c_uint32),
        ("bp_type", ctypes.c_uint32),
        ("bp_addr", ctypes.c_uint64),
        ("bp_len", ctypes.c_uint64),
    ]


def _perf_event_open(attr: _PerfEventAttr, pid: int, cpu: int) -> int:
    fd = _libc.syscall(__NR_perf_event_open, ctypes.byref(attr), pid, cpu, -1, 0)
    if fd < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    return fd


class HardwareCounter:
    """A single hardware PMU counter, opened for a specific (pid, cpu).

    Parameters
    ----------
    name : str
        Logical name (e.g. ``"cycles"``).
    config : int
        ``PERF_COUNT_HW_*`` constant.
    pid : int
        Target PID (``-1`` for system-wide, ``0`` for current process).
    cpu : int
        Target CPU (``-1`` for all CPUs).
    """

    __slots__ = ("_fd", "_name")

    def __init__(
        self,
        name: str,
        config: int,
        pid: int = -1,
        cpu: int = -1,
        *,
        disabled: bool = False,
    ):
        self._name = name
        attr = _PerfEventAttr()
        attr.type = PERF_TYPE_HARDWARE
        attr.size = ctypes.sizeof(_PerfEventAttr)
        attr.config = config
        attr.flags = 1 if disabled else 0
        self._fd = _perf_event_open(attr, pid, cpu)

    def read(self) -> int:
        """Read the raw 64-bit counter value."""
        buf = os.read(self._fd, 8)
        return struct.unpack("Q", buf)[0]

    def enable(self) -> None:
        """Start or resume counting."""
        fcntl.ioctl(self._fd, PERF_EVENT_IOC_ENABLE)

    def disable(self) -> None:
        """Pause counting."""
        fcntl.ioctl(self._fd, PERF_EVENT_IOC_DISABLE)

    def reset(self) -> None:
        """Zero the counter."""
        fcntl.ioctl(self._fd, PERF_EVENT_IOC_RESET)

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __del__(self) -> None:
        if hasattr(self, "_fd"):
            self.close()

    @property
    def fd(self) -> int:
        return self._fd

    @property
    def name(self) -> str:
        return self._name


# ---- module-level convenience (dashboard use) --------------------------------

_prev_values: dict[str, int] = {}
_prev_time: float = 0.0
_counters: list[HardwareCounter] = []
_available: bool | None = None


_COUNTER_SPECS: list[tuple[str, int]] = [
    ("cycles", PERF_COUNT_HW_CPU_CYCLES),
    ("instructions", PERF_COUNT_HW_INSTRUCTIONS),
    ("cache_misses", PERF_COUNT_HW_CACHE_MISSES),
]


def _ensure_counters() -> bool:
    global _available, _counters
    if _available is not None:
        return _available
    if _counters:
        _available = True
        return True
    opened: list[HardwareCounter] = []
    try:
        for name, config in _COUNTER_SPECS:
            opened.append(HardwareCounter(name, config, pid=-1, cpu=-1))
    except OSError:
        for c in opened:
            c.close()
        _available = False
        return False
    _counters = opened
    _available = True
    return True


def collect() -> dict[str, Any]:
    """Collect hardware PMU counter deltas since the last call.

    Returns
    -------
    dict with keys:
        available       bool   — True if PMU counters are accessible
        cycles          int    — CPU cycles elapsed since last poll
        instructions    int    — instructions retired since last poll
        cache_misses    int    — LLC misses since last poll
        ipc             float  — instructions per cycle
        cycles_per_sec  float  — cycle rate (GHz)
        inst_per_sec    float  — instruction rate (GIPS)
        miss_per_sec    float  — cache miss rate (M/s)
    """
    now = time.monotonic()
    result: dict[str, Any] = {
        "available": False,
        "cycles": 0,
        "instructions": 0,
        "cache_misses": 0,
        "ipc": 0.0,
        "cycles_per_sec": 0.0,
        "inst_per_sec": 0.0,
        "miss_per_sec": 0.0,
    }

    if not _ensure_counters():
        return result

    global _prev_values, _prev_time
    current: dict[str, int] = {}

    for c in _counters:
        try:
            current[c.name] = c.read()
        except OSError:
            return result

    if _prev_time > 0:
        dt = now - _prev_time
        if dt > 0:
            for name in ("cycles", "instructions", "cache_misses"):
                delta = current.get(name, 0) - _prev_values.get(name, 0)
                result[name] = max(0, delta)

            inst = result["instructions"]
            cycles = result["cycles"]
            misses = result["cache_misses"]

            result["ipc"] = inst / cycles if cycles > 0 else 0.0
            result["cycles_per_sec"] = cycles / dt
            result["inst_per_sec"] = inst / dt
            result["miss_per_sec"] = misses / dt
            result["available"] = True

    _prev_values = current
    _prev_time = now
    return result


def close() -> None:
    for c in _counters:
        c.close()
    _counters.clear()
    _prev_values.clear()
    global _prev_time
    _prev_time = 0.0

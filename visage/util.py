"""Shared formatting utilities."""

from collections import deque
from typing import Sequence


def format_bytes(n: float) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f} GB"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f} MB"
    if n >= 1_000:
        return f"{n / 1_000:.0f} KB"
    return f"{n:.0f} B"


def format_rate(bps: float) -> str:
    if bps >= 1_000_000_000:
        return f"{bps / 1_000_000_000:.1f} GB/s"
    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.0f} MB/s"
    if bps >= 1_000:
        return f"{bps / 1_000:.0f} KB/s"
    return f"{bps:.0f} B/s"


def format_percent(p: float) -> str:
    return f"{p:.1f}%"


def shorten_name(name: str, max_len: int = 18) -> str:
    if len(name) > max_len:
        return name[: max_len - 1] + "\u2026"
    return name


class DeltaTracker:
    """Compute deltas between successive collections for rate computation."""

    def __init__(self) -> None:
        self._prev: dict[str, float] = {}

    def update(self, current: dict[str, float]) -> dict[str, float]:
        if not self._prev:
            self._prev = {k: float(v) for k, v in current.items()}
            return {k: 0.0 for k in current}
        result = {
            k: float(v) - self._prev.get(k, float(v))
            for k, v in current.items()
        }
        self._prev = {k: float(v) for k, v in current.items()}
        return result


class HistoryBuffer:
    """Rolling window of the last N values for sparkline rendering."""

    __slots__ = ("_buf", "_maxlen")

    def __init__(self, maxlen: int = 60):
        self._buf: deque[float] = deque(maxlen=maxlen)
        self._maxlen = maxlen

    def push(self, value: float) -> None:
        self._buf.append(value)

    @property
    def values(self) -> list[float]:
        return list(self._buf)

    @property
    def full(self) -> bool:
        return len(self._buf) == self._maxlen

    def normalize(self) -> list[float]:
        vals = self.values
        if not vals:
            return []
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi > lo else 1.0
        return [(v - lo) / span for v in vals]


_SPARKLINE_CHARS = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"


def render_sparkline(values: list[float], width: int = 12) -> str:
    """Render normalised floats (0..1) as a Unicode sparkline bar."""
    if not values or width < 1:
        return ""
    n = len(values)
    if n < 2:
        return _SPARKLINE_CHARS[7]
    if width > n:
        width = n
    if width == 1:
        indices = [0]
    else:
        indices = [round(i * (n - 1) / (width - 1)) for i in range(width)]
    chars = [_SPARKLINE_CHARS[min(7, max(0, round(values[i] * 7)))] for i in indices]
    return "".join(chars)

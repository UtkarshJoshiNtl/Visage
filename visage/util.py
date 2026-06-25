"""Shared formatting utilities."""

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

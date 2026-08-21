"""Shared formatting utilities."""

import os
import time
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
    """Compute per-second rates between successive counter snapshots.

    Deltas are divided by wall-clock time between updates so displayed
    rates stay correct when tick timing jitters (slow collection, manual
    refresh, interval changes). Counter resets clamp to 0 instead of
    going negative.
    """

    def __init__(self) -> None:
        self._prev: dict[str, float] = {}
        self._prev_time: float = 0.0

    def update(self, current: dict[str, float], *, now: float | None = None) -> dict[str, float]:
        if now is None:
            now = time.monotonic()
        if not self._prev:
            self._prev = {k: float(v) for k, v in current.items()}
            self._prev_time = now
            return {k: 0.0 for k in current}
        dt = now - self._prev_time
        result = {
            k: max(0.0, (float(v) - self._prev.get(k, float(v))) / dt) if dt > 0 else 0.0
            for k, v in current.items()
        }
        self._prev = {k: float(v) for k, v in current.items()}
        self._prev_time = now
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

    def normalize_pct(self) -> list[float]:
        """Normalize using fixed 0-100 scale for percentage values."""
        return [min(v / 100.0, 1.0) for v in self.values]


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


_BRAILLE_BASE = 0x2800
_BRAILLE_DOTS = [
    (0, 0), (0, 1), (0, 2), (1, 0),
    (1, 1), (1, 2), (0, 3), (1, 3),
]


def render_braille_graph(values: list[float], width: int = 20, height: int = 3) -> str:
    """Render normalised floats (0..1) as a braille graph.

    Each braille character is 2 dots wide and 4 dots tall.
    Returns a string of braille characters representing the graph.
    """
    if not values or width < 1 or height < 1:
        return ""

    n = len(values)
    if n < 2:
        if values:
            v = values[0]
            filled_rows = int(v * height)
            lines = []
            for row in range(height):
                line = ""
                for col in range(width):
                    if row >= (height - filled_rows):
                        line += chr(_BRAILLE_BASE + 0b00000011)
                    else:
                        line += " "
                lines.append(line)
            return "\n".join(lines)
        return ""

    if width > n:
        width = n

    indices = [round(i * (n - 1) / (width - 1)) if width > 1 else 0 for i in range(width)]
    col_values = [values[i] for i in indices]

    lines = []
    for row in range(height):
        line = ""
        for col_idx, v in enumerate(col_values):
            grid = [[0] * 2 for _ in range(4)]
            for gx in range(2):
                for gy in range(4):
                    gy_world = (row + gy / 3.0) / height
                    if gy_world >= (1.0 - v):
                        grid[gy][gx] = 1

            code = _BRAILLE_BASE
            for dot_idx, (bx, by) in enumerate(_BRAILLE_DOTS):
                if grid[by][bx]:
                    code |= (1 << dot_idx)
            line += chr(code)
        lines.append(line)

    return "\n".join(lines)


def detect_ascii_fallback() -> bool:
    """Detect if we're in an SSH session or terminal that lacks Unicode/braille support."""
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_CLIENT"):
        return True
    term = os.environ.get("TERM", "").lower()
    if "linux" in term and "256" not in term:
        return True
    locale = os.environ.get("LANG", "").lower()
    if locale and "utf" not in locale:
        return True
    return False


def get_graph_style(configured: str = "braille") -> str:
    """Get effective graph style, falling back to ASCII if needed."""
    if configured == "auto" or (configured == "braille" and detect_ascii_fallback()):
        return "ascii"
    return configured


def render_block_graph(values: list[float], width: int = 20, height: int = 3) -> str:
    """Render normalised floats (0..1) using half-block characters.

    Uses \u2584 (lower half) and \u2588 (full block) for vertical resolution.
    """
    if not values or width < 1 or height < 1:
        return ""

    n = len(values)
    if n < 2:
        v = values[0] if values else 0
        filled = int(v * height * 2)
        lines = []
        for row in range(height):
            line = ""
            for col in range(width):
                level = (height - 1 - row) * 2
                if filled > level + 1:
                    line += "\u2588"
                elif filled > level:
                    line += "\u2584"
                else:
                    line += " "
            lines.append(line)
        return "\n".join(lines)

    if width > n:
        width = n

    indices = [round(i * (n - 1) / (width - 1)) if width > 1 else 0 for i in range(width)]
    col_values = [values[i] for i in indices]

    lines = []
    for row in range(height):
        line = ""
        for v in col_values:
            filled_cells = v * height * 2
            cell_bottom = (height - 1 - row) * 2
            cell_top = cell_bottom + 1

            if filled_cells >= cell_top + 1:
                line += "\u2588"
            elif filled_cells > cell_bottom:
                line += "\u2584"
            else:
                line += " "
        lines.append(line)

    return "\n".join(lines)

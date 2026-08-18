"""CPU usage widget — progress bar, percentage, per-core breakdown."""

from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Label, ProgressBar, Static
from textual.widget import Widget

from visage.util import HistoryBuffer, format_percent, render_sparkline


def _fmt_uptime(seconds: float) -> str:
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    mins = int((seconds % 3600) // 60)
    if days > 0:
        return f"{days}d {hours}h {mins}m"
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


class CpuWidget(Widget):
    percent: float = reactive(0.0)
    per_cpu: list[float] = reactive([])

    def __init__(self):
        super().__init__()
        self._cpu_hist = HistoryBuffer(60)
        self._red = 80.0
        self._yellow = 50.0
        self._model = ""
        self._freq_cur = 0.0
        self._freq_min = 0.0
        self._freq_max = 0.0
        self._uptime = 0.0
        self._ctx_per_sec = 0.0
        self._intr_per_sec = 0.0

    def set_thresholds(self, t: dict) -> None:
        self._red = float(t.get("red", self._red))
        self._yellow = float(t.get("yellow", self._yellow))

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("CPU", id="cpu-title", classes="metric-title")
            yield Static(id="cpu-info", classes="metric-detail")
            with Horizontal(classes="metric-bar-row"):
                yield ProgressBar(
                    id="cpu-bar",
                    total=100,
                    show_eta=False,
                    show_percentage=False,
                )
                yield Static(id="cpu-pct", classes="metric-value")
            yield Static(id="cpu-freq", classes="metric-detail")
            yield Static(id="cpu-detail", classes="metric-detail")
            yield Static(id="cpu-stats", classes="metric-detail")

    def on_mount(self) -> None:
        self._title = self.query_one("#cpu-title", Label)
        self._info = self.query_one("#cpu-info", Static)
        self._bar = self.query_one("#cpu-bar", ProgressBar)
        self._pct = self.query_one("#cpu-pct", Static)
        self._freq_label = self.query_one("#cpu-freq", Static)
        self._detail = self.query_one("#cpu-detail", Static)
        self._stats = self.query_one("#cpu-stats", Static)

    def watch_percent(self, value: float) -> None:
        self._bar.progress = min(value, 100.0)
        spark = render_sparkline(self._cpu_hist.normalize(), 15)
        self._pct.update(f"{format_percent(value)}  {spark}")

    def watch_per_cpu(self, cores: list[float]) -> None:
        parts = []
        for i, p in enumerate(cores):
            label = f"C{i}:{p:.0f}%"
            if p >= self._red:
                parts.append(f"[red]{label}[/]")
            elif p >= self._yellow:
                parts.append(f"[yellow]{label}[/]")
            else:
                parts.append(f"[green]{label}[/]")
        detail = "  ".join(parts) if parts else ""
        self._detail.update(detail)

    def update_data(self, data: dict) -> None:
        self.percent = data["percent"]
        self._cpu_hist.push(data["percent"])
        self.per_cpu = data.get("per_cpu", [])

        model = data.get("model", "")
        if model and model != self._model:
            self._model = model
            if len(model) > 40:
                model = model[:39] + "\u2026"
            self._title.update(f"CPU  [dim]{model}[/]")

        uptime = data.get("uptime", 0.0)
        if uptime > 0:
            self._uptime = uptime
            self._info.update(f"Uptime: {_fmt_uptime(uptime)}")

        freq_cur = data.get("freq_current", 0.0)
        freq_min = data.get("freq_min", 0.0)
        freq_max = data.get("freq_max", 0.0)
        self._freq_cur = freq_cur
        self._freq_min = freq_min
        self._freq_max = freq_max
        if freq_cur > 0:
            parts = [f"[bold]{freq_cur:.0f}[/] MHz"]
            if freq_min > 0 and freq_max > 0:
                parts.append(f"({freq_min:.0f}\u2013{freq_max:.0f} MHz)")
            self._freq_label.update("Freq: " + " ".join(parts))
        else:
            self._freq_label.update("")

        ctx_ps = data.get("ctx_per_sec", 0.0)
        intr_ps = data.get("interrupts_per_sec", 0.0)
        soft_ps = data.get("soft_per_sec", 0.0)
        if ctx_ps > 0:
            stat_parts = []
            if ctx_ps >= 1000:
                stat_parts.append(f"ctx: {ctx_ps / 1000:.1f}k/s")
            else:
                stat_parts.append(f"ctx: {ctx_ps:.0f}/s")
            if intr_ps >= 1000:
                stat_parts.append(f"intr: {intr_ps / 1000:.1f}k/s")
            else:
                stat_parts.append(f"intr: {intr_ps:.0f}/s")
            if soft_ps >= 1:
                stat_parts.append(f"softirq: {soft_ps:.0f}/s")
            self._stats.update("  ".join(stat_parts))
        else:
            self._stats.update("")

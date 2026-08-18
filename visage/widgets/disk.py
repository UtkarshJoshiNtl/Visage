"""Disk widget — per-partition read/write rates and usage."""

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Label, Static
from textual.widget import Widget

from visage.util import DeltaTracker, HistoryBuffer, format_bytes, format_rate, render_sparkline


def _usage_bar(pct: float, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    filled = max(0, min(filled, width))
    empty = width - filled
    if pct >= 90:
        color = "red"
    elif pct >= 75:
        color = "yellow"
    else:
        color = "green"
    bar = "\u2588" * filled + "\u2591" * empty
    return f"[{color}]{bar}[/{color}]"


class DiskWidget(Widget):
    read_rate: float = reactive(0.0)
    write_rate: float = reactive(0.0)

    def __init__(self):
        super().__init__()
        self._rd_hist = HistoryBuffer(60)
        self._wr_hist = HistoryBuffer(60)
        self._partitions: list[dict] = []
        self._perdisk_trackers: dict[str, DeltaTracker] = {}
        self._perdisk_rates: dict[str, dict[str, float]] = {}

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("Disk", classes="metric-title")
            yield Static(id="disk-total", classes="metric-detail")
            yield Static(id="disk-partitions", classes="metric-detail")

    def on_mount(self) -> None:
        self._total_label = self.query_one("#disk-total", Static)
        self._parts_label = self.query_one("#disk-partitions", Static)

    def update_data(self, data: dict) -> None:
        total = data.get("total", {})
        perdisk = data.get("perdisk", {})
        partitions = data.get("partitions", [])

        rd = total.get("read_bytes", 0.0)
        wr = total.get("write_bytes", 0.0)
        self._rd_hist.push(rd)
        self._wr_hist.push(wr)
        self.read_rate = rd
        self.write_rate = wr

        rd_spark = render_sparkline(self._rd_hist.normalize(), 12)
        wr_spark = render_sparkline(self._wr_hist.normalize(), 12)
        self._total_label.update(
            f"Total  Read:  [bold green]{format_rate(rd)}[/]  {rd_spark}\n"
            f"       Write: [bold yellow]{format_rate(wr)}[/]  {wr_spark}"
        )

        self._partitions = partitions
        lines: list[str] = []
        for p in partitions[:6]:
            mount = p.get("mount", "?")
            pct = p.get("percent", 0)
            total_b = p.get("total", 0)
            used_b = p.get("used", 0)
            dev = p.get("device", "")
            short_dev = dev.split("/")[-1] if "/" in dev else dev
            if len(short_dev) > 10:
                short_dev = short_dev[:9] + "\u2026"
            bar = _usage_bar(pct, 8)
            lines.append(
                f"  {short_dev:10s} {mount:16s} {bar} {pct:5.1f}%  "
                f"{format_bytes(used_b)}/{format_bytes(total_b)}"
            )

        if lines:
            self._parts_label.update("\n".join(lines))
        else:
            self._parts_label.update("[dim]  No partition data[/]")

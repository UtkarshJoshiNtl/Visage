"""Memory usage widget — progress bar with used/total and swap info."""

from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Label, ProgressBar, Static
from textual.widget import Widget

from visage.util import format_bytes, format_percent


class MemoryWidget(Widget):
    percent: float = reactive(0.0)
    used: int = reactive(0)
    total: int = reactive(0)
    swap_used: int = reactive(0)
    swap_total: int = reactive(0)

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("Memory", classes="metric-title")
            with Horizontal(classes="metric-bar-row"):
                yield ProgressBar(
                    id="mem-bar",
                    total=100,
                    show_eta=False,
                    show_percentage=False,
                )
                yield Static(id="mem-pct", classes="metric-value")
            yield Static(id="mem-detail", classes="metric-detail")

    def watch_percent(self, value: float) -> None:
        self.query_one("#mem-bar", ProgressBar).progress = min(value, 100.0)
        used_fmt = format_bytes(self.used)
        total_fmt = format_bytes(self.total)
        self.query_one("#mem-pct", Static).update(format_percent(value))

    def watch_used(self, _: int) -> None:
        used_fmt = format_bytes(self.used)
        total_fmt = format_bytes(self.total)
        swap = ""
        if self.swap_total > 0:
            swap = f"  Swap: {format_bytes(self.swap_used)} / {format_bytes(self.swap_total)}"
        self.query_one("#mem-detail", Static).update(
            f"{used_fmt} / {total_fmt}{swap}"
        )

    def update_data(self, data: dict) -> None:
        self.percent = data["percent"]
        self.used = data["used"]
        self.total = data["total"]
        self.swap_used = data["swap_used"]
        self.swap_total = data["swap_total"]

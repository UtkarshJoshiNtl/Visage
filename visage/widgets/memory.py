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

    def on_mount(self) -> None:
        self._bar = self.query_one("#mem-bar", ProgressBar)
        self._pct = self.query_one("#mem-pct", Static)
        self._detail = self.query_one("#mem-detail", Static)

    def watch_percent(self, value: float) -> None:
        self._bar.progress = min(value, 100.0)
        self._pct.update(format_percent(value))

    def watch_used(self, _: int) -> None:
        self._refresh_detail()

    def watch_total(self, _: int) -> None:
        self._refresh_detail()

    def _refresh_detail(self) -> None:
        used_fmt = format_bytes(self.used)
        total_fmt = format_bytes(self.total)
        swap = ""
        if self.swap_total > 0:
            swap = f"  Swap: {format_bytes(self.swap_used)} / {format_bytes(self.swap_total)}"
        self._detail.update(f"{used_fmt} / {total_fmt}{swap}")

    def update_data(self, data: dict) -> None:
        self.percent = data["percent"]
        self.used = data["used"]
        self.total = data["total"]
        self.swap_used = data["swap_used"]
        self.swap_total = data["swap_total"]

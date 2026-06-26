"""Disk I/O widget — read/write throughput rates."""

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Label, Static
from textual.widget import Widget

from visage.util import format_rate


class DiskWidget(Widget):
    read_rate: float = reactive(0.0)
    write_rate: float = reactive(0.0)
    read_count_rate: float = reactive(0.0)
    write_count_rate: float = reactive(0.0)

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("Disk", classes="metric-title")
            yield Static(id="disk-content", classes="metric-detail")

    def on_mount(self) -> None:
        self._content = self.query_one("#disk-content", Static)

    def watch_read_rate(self, _: float) -> None:
        self._update()

    def watch_write_rate(self, _: float) -> None:
        self._update()

    def _update(self) -> None:
        self._content.update(
            f"Read:  [bold green]{format_rate(self.read_rate)}[/]"
            f"   Write: [bold yellow]{format_rate(self.write_rate)}[/]"
        )

    def update_data(self, data: dict) -> None:
        self.read_rate = data.get("read_bytes", 0.0)
        self.write_rate = data.get("write_bytes", 0.0)
        self.read_count_rate = data.get("read_count", 0.0)
        self.write_count_rate = data.get("write_count", 0.0)

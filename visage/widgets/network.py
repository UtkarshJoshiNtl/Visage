"""Network I/O widget — download/upload throughput rates."""

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Label, Static
from textual.widget import Widget

from visage.util import HistoryBuffer, format_rate, render_sparkline


class NetworkWidget(Widget):
    down_rate: float = reactive(0.0)
    up_rate: float = reactive(0.0)

    def __init__(self):
        super().__init__()
        self._down_hist = HistoryBuffer(60)
        self._up_hist = HistoryBuffer(60)

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("Network", classes="metric-title")
            yield Static(id="net-content", classes="metric-detail")

    def on_mount(self) -> None:
        self._content = self.query_one("#net-content", Static)

    def watch_down_rate(self, _: float) -> None:
        self._update()

    def watch_up_rate(self, _: float) -> None:
        self._update()

    def _update(self) -> None:
        down_spark = render_sparkline(self._down_hist.normalize(), 12)
        up_spark = render_sparkline(self._up_hist.normalize(), 12)
        self._content.update(
            f"[bold green]\u2193 {format_rate(self.down_rate)}[/]  {down_spark}\n"
            f"[bold yellow]\u2191 {format_rate(self.up_rate)}[/]  {up_spark}"
        )

    def update_data(self, data: dict) -> None:
        self._down_hist.push(data.get("bytes_recv", 0.0))
        self._up_hist.push(data.get("bytes_sent", 0.0))
        self.down_rate = data.get("bytes_recv", 0.0)
        self.up_rate = data.get("bytes_sent", 0.0)

"""Network widget — per-interface download/upload throughput rates."""

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Label, Static
from textual.widget import Widget

from visage.util import HistoryBuffer, format_rate, render_sparkline


def _fmt_rate(bps: float) -> str:
    if bps >= 1_000_000_000:
        return f"{bps / 1_000_000_000:.1f}Gb/s"
    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.1f}Mb/s"
    if bps >= 1_000:
        return f"{bps / 1_000:.0f}Kb/s"
    return f"{bps:.0f}b/s"


class NetworkWidget(Widget):
    down_rate: float = reactive(0.0)
    up_rate: float = reactive(0.0)

    def __init__(self):
        super().__init__()
        self._down_hist = HistoryBuffer(60)
        self._up_hist = HistoryBuffer(60)
        self._iface_data: dict[str, dict] = {}
        self._iface_down_hist: dict[str, HistoryBuffer] = {}
        self._iface_up_hist: dict[str, HistoryBuffer] = {}

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("Network", classes="metric-title")
            yield Static(id="net-total", classes="metric-detail")
            yield Static(id="net-interfaces", classes="metric-detail")

    def on_mount(self) -> None:
        self._total_label = self.query_one("#net-total", Static)
        self._iface_label = self.query_one("#net-interfaces", Static)

    def update_data(self, data: dict) -> None:
        total = data.get("total", {})
        pernic = data.get("pernic", {})

        down = total.get("bytes_recv", 0.0)
        up = total.get("bytes_sent", 0.0)
        self._down_hist.push(down)
        self._up_hist.push(up)
        self.down_rate = down
        self.up_rate = up

        down_spark = render_sparkline(self._down_hist.normalize(), 12)
        up_spark = render_sparkline(self._up_hist.normalize(), 12)
        self._total_label.update(
            f"[bold green]\u2193 {_fmt_rate(down)}[/]  {down_spark}\n"
            f"[bold yellow]\u2191 {_fmt_rate(up)}[/]  {up_spark}"
        )

        lines: list[str] = []
        for name, info in list(pernic.items())[:8]:
            ip = info.get("ip", "")
            ip_short = ip[:15] if ip else ""
            lines.append(
                f"  [bold]{name:12s}[/] {ip_short:15s} "
                f"\u2193{_fmt_rate(info.get('bytes_recv', 0)):>10s}  "
                f"\u2191{_fmt_rate(info.get('bytes_sent', 0)):>10s}"
            )

        if lines:
            self._iface_label.update("\n".join(lines))
        else:
            self._iface_label.update("[dim]  No interface data[/]")

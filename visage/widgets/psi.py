"""PSI (Pressure Stall Information) widget — sparklines for CPU/memory/IO pressure."""

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Label, Static
from textual.widget import Widget

from visage.util import HistoryBuffer, format_percent, render_sparkline


class PsiWidget(Widget):
    cpu_some: float = reactive(0.0)
    mem_some: float = reactive(0.0)
    mem_full: float = reactive(0.0)
    io_some: float = reactive(0.0)
    io_full: float = reactive(0.0)

    def __init__(self):
        super().__init__()
        self._cpu_hist = HistoryBuffer(60)
        self._mem_some_hist = HistoryBuffer(60)
        self._mem_full_hist = HistoryBuffer(60)
        self._io_some_hist = HistoryBuffer(60)
        self._io_full_hist = HistoryBuffer(60)
        self._available = True

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("Pressure (PSI)", id="psi-title", classes="metric-title")
            yield Static(id="psi-cpu", classes="metric-detail")
            yield Static(id="psi-mem", classes="metric-detail")
            yield Static(id="psi-io", classes="metric-detail")

    def on_mount(self) -> None:
        self._cpu_label = self.query_one("#psi-cpu", Static)
        self._mem_label = self.query_one("#psi-mem", Static)
        self._io_label = self.query_one("#psi-io", Static)

    def watch_cpu_some(self, value: float) -> None:
        self._render_line(self._cpu_label, "CPU", value, None, self._cpu_hist)

    def watch_mem_some(self, value: float) -> None:
        self._render_mem()

    def watch_mem_full(self, value: float) -> None:
        self._render_mem()

    def watch_io_some(self, value: float) -> None:
        self._render_io()

    def watch_io_full(self, value: float) -> None:
        self._render_io()

    def _render_mem(self) -> None:
        some = self.mem_some
        full = self.mem_full
        some_spark = render_sparkline(self._mem_some_hist.normalize_pct(), 15)
        full_spark = render_sparkline(self._mem_full_hist.normalize_pct(), 15)
        parts = [
            f"[bold]Mem some:[/] {format_percent(some)} {some_spark}",
        ]
        if full > 0 or self._mem_full_hist.full:
            parts.append(f"[bold]full:[/] {format_percent(full)} {full_spark}")
        self._mem_label.update("  ".join(parts))

    def _render_io(self) -> None:
        some = self.io_some
        full = self.io_full
        some_spark = render_sparkline(self._io_some_hist.normalize_pct(), 15)
        full_spark = render_sparkline(self._io_full_hist.normalize_pct(), 15)
        parts = [
            f"[bold]I/O some:[/] {format_percent(some)} {some_spark}",
        ]
        if full > 0 or self._io_full_hist.full:
            parts.append(f"[bold]full:[/] {format_percent(full)} {full_spark}")
        self._io_label.update("  ".join(parts))

    def _render_line(self, widget: Static, label: str, some_val: float, full_val: float | None, hist: HistoryBuffer) -> None:
        spark = render_sparkline(hist.normalize_pct(), 15)
        parts = [f"[bold]{label} some:[/] {format_percent(some_val)} {spark}"]
        if full_val is not None:
            full_spark = render_sparkline(self._cpu_hist.normalize_pct(), 15)
            parts.append(f"[bold]full:[/] {format_percent(full_val)} {full_spark}")
        widget.update("  ".join(parts))

    def update_data(self, data: dict) -> None:
        if not data.get("available", False):
            self._available = False
            self.query_one("#psi-title", Label).update("Pressure (PSI)  [dim]unavailable[/]")
            return

        cpu_data = data.get("cpu", {})
        cpu_some = cpu_data.get("some", {}).get("avg10", 0.0)
        self._cpu_hist.push(cpu_some)
        self.cpu_some = cpu_some

        mem_data = data.get("memory", {})
        mem_some = mem_data.get("some", {}).get("avg10", 0.0)
        mem_full = mem_data.get("full", {}).get("avg10", 0.0)
        self._mem_some_hist.push(mem_some)
        self._mem_full_hist.push(mem_full)
        self.mem_some = mem_some
        self.mem_full = mem_full

        io_data = data.get("io", {})
        io_some = io_data.get("some", {}).get("avg10", 0.0)
        io_full = io_data.get("full", {}).get("avg10", 0.0)
        self._io_some_hist.push(io_some)
        self._io_full_hist.push(io_full)
        self.io_some = io_some
        self.io_full = io_full

"""Process table widget — top processes by CPU usage."""

from typing import Any

from rich.table import Table
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Label, Static
from textual.widget import Widget


class ProcessesWidget(Widget):
    processes: list[dict[str, Any]] = reactive([])

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("Processes", classes="metric-title")
            yield Static(id="proc-table", classes="metric-detail")

    def on_mount(self) -> None:
        self._table = self.query_one("#proc-table", Static)

    def watch_processes(self, procs: list[dict[str, Any]]) -> None:
        table = Table(box=None, padding=(0, 1), show_header=False)
        table.add_column("Name", no_wrap=True, style="bold")
        table.add_column("CPU%", justify="right", style="yellow")
        table.add_column("Mem%", justify="right", style="cyan")

        for p in procs:
            name = p["name"]
            if len(name) > 20:
                name = name[:19] + "\u2026"
            table.add_row(name, f"{p['cpu']:.1f}", f"{p['memory']:.1f}")

        if not procs:
            table.add_row("(no data)", "", "")

        self._table.update(table)

    def update_data(self, data: list[dict[str, Any]]) -> None:
        self.processes = data

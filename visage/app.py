"""Visage — system performance dashboard main application."""

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header

from visage.collectors import cpu as cpu_col
from visage.collectors import disk as disk_col
from visage.collectors import memory as mem_col
from visage.collectors import network as net_col
from visage.collectors import process as proc_col
from visage.util import DeltaTracker
from visage.widgets.cpu import CpuWidget
from visage.widgets.disk import DiskWidget
from visage.widgets.memory import MemoryWidget
from visage.widgets.network import NetworkWidget
from visage.widgets.processes import ProcessesWidget


class VisageApp(App):
    """Live terminal dashboard for system performance metrics."""

    TITLE = "Visage"
    CSS_PATH = "style.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_now", "Refresh"),
        ("d", "cycle_delay", "Speed"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._interval = 1.0
        self._disk_tracker = DeltaTracker()
        self._net_tracker = DeltaTracker()

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="dashboard"):
            yield CpuWidget()
            yield MemoryWidget()
            yield DiskWidget()
            yield NetworkWidget()
            yield ProcessesWidget()
        yield Footer()

    def on_mount(self) -> None:
        self.poll()
        self.set_interval(self._interval, self.poll)

    def poll(self) -> None:
        cpu_data = cpu_col.collect()
        self.query_one(CpuWidget).update_data(cpu_data)

        mem_data = mem_col.collect()
        self.query_one(MemoryWidget).update_data(mem_data)

        disk_raw = disk_col.collect()
        disk_delta = self._disk_tracker.update(disk_raw)
        self.query_one(DiskWidget).update_data(disk_delta)

        net_raw = net_col.collect()
        net_delta = self._net_tracker.update(net_raw)
        self.query_one(NetworkWidget).update_data(net_delta)

        proc_data = proc_col.collect()
        self.query_one(ProcessesWidget).update_data(proc_data)

    def action_refresh_now(self) -> None:
        self.poll()

    def action_cycle_delay(self) -> None:
        speeds = {0.5: "0.5s", 1.0: "1s", 2.0: "2s", 5.0: "5s"}
        current = list(speeds.keys())
        idx = current.index(self._interval) if self._interval in current else 1
        self._interval = current[(idx + 1) % len(current)]
        self.notify(f"Refresh: {speeds[self._interval]}", timeout=2)
        self.set_interval(self._interval, self.poll)

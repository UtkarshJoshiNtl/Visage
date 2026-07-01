"""Visage — system performance dashboard main application."""

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header
from textual import work

from visage.collectors import cpu as cpu_col
from visage.collectors import disk as disk_col
from visage.collectors import memory as mem_col
from visage.collectors import network as net_col
from visage.collectors import gpu as gpu_col
from visage.collectors import process as proc_col
from visage.alert import AlertEngine
from visage.config import load_config
from visage.util import DeltaTracker
from visage.widgets.cpu import CpuWidget
from visage.widgets.disk import DiskWidget
from visage.widgets.gpu import GpuWidget
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

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__()
        self._cfg = load_config(config_path)
        self._interval = self._cfg.refresh_interval
        self._disk_tracker = DeltaTracker()
        self._net_tracker = DeltaTracker()
        self._sys_timer = None
        self._alert_engine = AlertEngine()
        self._alert_engine.set_rules(self._cfg.alerts)
        self._alert_engine.set_action(self._fire_alert)

    _WIDGET_CLASSES = {
        "cpu": CpuWidget,
        "memory": MemoryWidget,
        "disk": DiskWidget,
        "network": NetworkWidget,
        "gpu": GpuWidget,
        "processes": ProcessesWidget,
    }

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="dashboard"):
            shown = set(self._cfg.enabled_widgets)
            for name in self._cfg.widget_order:
                if name in shown:
                    cls = self._WIDGET_CLASSES.get(name)
                    if cls:
                        yield cls()
        yield Footer()

    def on_mount(self) -> None:
        self._cpu_widget = self.query_one(CpuWidget)
        self._mem_widget = self.query_one(MemoryWidget)
        self._disk_widget = self.query_one(DiskWidget)
        self._net_widget = self.query_one(NetworkWidget)
        self._gpu_widget = self.query_one(GpuWidget)
        self._proc_widget = self.query_one(ProcessesWidget)

        self._cpu_widget.set_thresholds(self._cfg.thresholds.get("cpu", {}))
        self._mem_widget.set_thresholds(self._cfg.thresholds.get("memory", {}))
        self._gpu_widget.set_thresholds(self._cfg.thresholds)

        cpu_col.collect()
        gpu_col.collect()
        self._disk_tracker.update(disk_col.collect())
        self._net_tracker.update(net_col.collect())

        self.fetch_system_metrics()
        self._sys_timer = self.set_interval(self._interval, self.fetch_system_metrics)
        self.set_interval(2.0, self.fetch_process_metrics)

    def _fire_alert(self, message: str) -> None:
        self.notify(message, timeout=5)

    @work(thread=True, exclusive=True, group="system")
    def fetch_system_metrics(self) -> None:
        cpu_data = cpu_col.collect()
        mem_data = mem_col.collect()
        disk_raw = disk_col.collect()
        disk_delta = self._disk_tracker.update(disk_raw)
        net_raw = net_col.collect()
        net_delta = self._net_tracker.update(net_raw)
        gpu_data = gpu_col.collect()

        snapshot = {
            "cpu_percent": cpu_data.get("percent", 0.0),
            "mem_percent": mem_data.get("percent", 0.0),
            "gpu_sm_util": gpu_data.get("sm_util", 0.0),
            "gpu_mem_util": gpu_data.get("mem_util", 0.0),
            "gpu_temp_c": gpu_data.get("temp_c", 0.0),
            "gpu_power_w": gpu_data.get("power_w", 0.0),
        }
        self._alert_engine.evaluate(snapshot)

        self.call_from_thread(
            self._update_system_ui, cpu_data, mem_data, disk_delta, net_delta, gpu_data
        )

    @work(thread=True, exclusive=True, group="process")
    def fetch_process_metrics(self) -> None:
        proc_data = proc_col.collect()
        self.call_from_thread(self._proc_widget.update_data, proc_data)

    def _update_system_ui(
        self,
        cpu_data: dict,
        mem_data: dict,
        disk_delta: dict,
        net_delta: dict,
        gpu_data: dict,
    ) -> None:
        self._cpu_widget.update_data(cpu_data)
        self._mem_widget.update_data(mem_data)
        self._disk_widget.update_data(disk_delta)
        self._net_widget.update_data(net_delta)
        self._gpu_widget.update_data(gpu_data)

    def action_refresh_now(self) -> None:
        self.fetch_system_metrics()
        self.fetch_process_metrics()

    def action_cycle_delay(self) -> None:
        speeds = {0.5: "0.5s", 1.0: "1s", 2.0: "2s", 5.0: "5s"}
        current = list(speeds.keys())
        idx = current.index(self._interval) if self._interval in current else 1
        self._interval = current[(idx + 1) % len(current)]
        self.notify(f"Refresh: {speeds[self._interval]}", timeout=2)
        if self._sys_timer is not None:
            self._sys_timer.remove()
        self._sys_timer = self.set_interval(self._interval, self.fetch_system_metrics)

"""Visage — system performance dashboard main application."""

import os
from pathlib import Path

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
from visage.collectors.sensors import collect as collect_sensors
from visage.collectors.battery import collect as collect_battery
from visage.collectors.docker import collect as collect_docker
from visage.collectors.psi import collect as collect_psi
from visage.alert import AlertEngine
from visage.config import load_config
from visage.theme import list_themes, get_theme, get_default_theme, generate_tcss
from visage.util import DeltaTracker, get_graph_style
from visage.widgets.cpu import CpuWidget
from visage.widgets.disk import DiskWidget
from visage.widgets.gpu import GpuWidget
from visage.widgets.memory import MemoryWidget
from visage.widgets.network import NetworkWidget
from visage.widgets.processes import ProcessesWidget
from visage.widgets.sensors import SensorsWidget
from visage.widgets.battery import BatteryWidget
from visage.widgets.docker import DockerWidget
from visage.widgets.psi import PsiWidget


class VisageApp(App):
    """Live terminal dashboard for system performance metrics."""

    TITLE = "Visage"
    CSS_PATH = "style.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_now", "Refresh"),
        ("d", "cycle_delay", "Speed"),
        ("t", "cycle_theme", "Theme"),
        ("g", "cycle_gpu", "GPU"),
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
        self._widgets: dict[str, object] = {}
        self._theme_names = list_themes()
        self._theme_idx = 0
        self._graph_style = get_graph_style(self._cfg.graph_style)
        self._active_timers: list = []

        if self._cfg.theme in self._theme_names:
            self._theme_idx = self._theme_names.index(self._cfg.theme)

        cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "visage"
        cached_css = cache_dir / "style.tcss"
        if cached_css.exists():
            self.CSS_PATH = str(cached_css)
        elif not (Path(__file__).parent / "style.tcss").exists():
            self.CSS = ""

    _WIDGET_CLASSES = {
        "cpu": CpuWidget,
        "memory": MemoryWidget,
        "disk": DiskWidget,
        "network": NetworkWidget,
        "gpu": GpuWidget,
        "psi": PsiWidget,
        "sensors": SensorsWidget,
        "battery": BatteryWidget,
        "docker": DockerWidget,
        "processes": ProcessesWidget,
    }

    _COLLECTOR_TIMERS: dict[str, tuple[str, float, str]] = {
        "processes": ("fetch_process_metrics", 2.0, "process"),
        "sensors": ("fetch_sensor_metrics", 9.0, "sensor"),
        "battery": ("fetch_battery_metrics", 5.0, "battery"),
        "docker": ("fetch_docker_metrics", 3.0, "docker"),
        "psi": ("fetch_psi_metrics", 6.0, "psi"),
    }

    def _widget(self, name: str):
        return self._widgets.get(name)

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
        self._widgets: dict[str, object] = {}
        for name, cls in self._WIDGET_CLASSES.items():
            found = self.query(cls)
            if found:
                self._widgets[name] = found.first()

        for name in ("cpu", "memory", "gpu"):
            widget = self._widget(name)
            if widget is None:
                continue
            if name == "gpu":
                widget.set_thresholds(self._cfg.thresholds)
            else:
                widget.set_thresholds(self._cfg.thresholds.get(name, {}))

        cpu_col.collect()
        gpu_col.collect()
        disk_snapshot = disk_col.collect()
        self._disk_tracker.update(disk_snapshot.get("total", {}))
        net_snapshot = net_col.collect()
        net_total = net_snapshot.get("total", {})
        net_delta = self._net_tracker.update(net_total)
        net_widget_data = {
            "total": net_delta,
            "pernic": net_snapshot.get("pernic", {}),
        }

        self.fetch_system_metrics()
        self._active_timers.append(
            self.set_interval(self._interval, self.fetch_system_metrics)
        )

        shown = set(self._cfg.enabled_widgets)
        for widget_name, (method_name, interval, _group) in self._COLLECTOR_TIMERS.items():
            if widget_name in shown:
                fn = getattr(self, method_name)
                self._active_timers.append(self.set_interval(interval, fn))

    def _apply_theme(self, theme_name: str) -> None:
        theme = get_theme(theme_name) or get_default_theme()
        tcss = generate_tcss(theme)
        try:
            cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "visage"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / "style.tcss"
            cache_path.write_text(tcss)
            self.CSS_PATH = str(cache_path)
        except Exception as e:
            self.notify(f"Theme failed: {e}", severity="warning", timeout=5)
        self.refresh()

    def _fire_alert(self, message: str) -> None:
        self.call_from_thread(self.notify, message, timeout=5)

    @work(thread=True, exclusive=True, group="system")
    def fetch_system_metrics(self) -> None:
        cpu_data = cpu_col.collect()
        mem_data = mem_col.collect()
        disk_snapshot = disk_col.collect()
        disk_total = disk_snapshot.get("total", {})
        disk_delta = self._disk_tracker.update(disk_total)
        disk_widget_data = {
            "total": disk_delta,
            "perdisk": disk_snapshot.get("perdisk", {}),
            "partitions": disk_snapshot.get("partitions", []),
        }
        net_raw = net_col.collect()
        net_total = net_raw.get("total", {})
        net_delta = self._net_tracker.update(net_total)
        net_widget_data = {
            "total": net_delta,
            "pernic": net_raw.get("pernic", {}),
        }
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
            self._update_system_ui, cpu_data, mem_data, disk_widget_data, net_widget_data, gpu_data
        )

    @work(thread=True, exclusive=True, group="process")
    def fetch_process_metrics(self) -> None:
        proc_widget = self._widget("processes")
        if proc_widget is None:
            return
        proc_data = proc_col.collect(
            top_n=30,
            sort_by=proc_widget.sort_by,
            sort_reverse=proc_widget.sort_reverse,
            filter_str=proc_widget.filter_str,
            tree_mode=proc_widget.tree_mode,
            aggregate_mode=proc_widget.aggregate_mode,
        )
        self.call_from_thread(proc_widget.update_data, proc_data)

    @work(thread=True, exclusive=True, group="sensor")
    def fetch_sensor_metrics(self) -> None:
        sensor_widget = self._widget("sensors")
        if sensor_widget is None:
            return
        sensor_data = collect_sensors()
        self.call_from_thread(sensor_widget.update_data, sensor_data)

    @work(thread=True, exclusive=True, group="battery")
    def fetch_battery_metrics(self) -> None:
        bat_widget = self._widget("battery")
        if bat_widget is None:
            return
        bat_data = collect_battery()
        self.call_from_thread(bat_widget.update_data, bat_data)

    @work(thread=True, exclusive=True, group="docker")
    def fetch_docker_metrics(self) -> None:
        docker_widget = self._widget("docker")
        if docker_widget is None:
            return
        docker_data = collect_docker()
        self.call_from_thread(docker_widget.update_data, docker_data)

    @work(thread=True, exclusive=True, group="psi")
    def fetch_psi_metrics(self) -> None:
        psi_widget = self._widget("psi")
        if psi_widget is None:
            return
        psi_data = collect_psi()
        self.call_from_thread(psi_widget.update_data, psi_data)

    def _update_system_ui(
        self,
        cpu_data: dict,
        mem_data: dict,
        disk_delta: dict,
        net_delta: dict,
        gpu_data: dict,
    ) -> None:
        for name, data in (
            ("cpu", cpu_data),
            ("memory", mem_data),
            ("disk", disk_delta),
            ("network", net_delta),
            ("gpu", gpu_data),
        ):
            widget = self._widget(name)
            if widget is not None:
                widget.update_data(data)

    def action_refresh_now(self) -> None:
        self.fetch_system_metrics()
        self.fetch_process_metrics()
        self.fetch_sensor_metrics()

    def action_cycle_delay(self) -> None:
        speeds = {0.5: "0.5s", 1.0: "1s", 2.0: "2s", 5.0: "5s"}
        current = list(speeds.keys())
        idx = current.index(self._interval) if self._interval in current else 1
        self._interval = current[(idx + 1) % len(current)]
        self.notify(f"Refresh: {speeds[self._interval]}", timeout=2)
        if self._sys_timer is not None:
            self._sys_timer.stop()
        self._sys_timer = self.set_interval(self._interval, self.fetch_system_metrics)

    def action_cycle_theme(self) -> None:
        if not self._theme_names:
            self.notify("No themes available", timeout=2)
            return
        self._theme_idx = (self._theme_idx + 1) % len(self._theme_names)
        name = self._theme_names[self._theme_idx]
        theme = get_theme(name)
        display = theme.display_name if theme else name
        self._apply_theme(name)
        self.notify(f"Theme: {display}", timeout=2)

    def action_cycle_gpu(self) -> None:
        gpu_widget = self._widget("gpu")
        if gpu_widget is not None and getattr(gpu_widget, "available", False):
            gpu_widget.cycle_gpu()
            self.notify(
                f"Active GPU: {gpu_widget.active_gpu_idx + 1}/{gpu_widget.gpu_count} ({gpu_widget.name})",
                timeout=2,
            )
        else:
            self.notify("No active GPU to switch", timeout=2)

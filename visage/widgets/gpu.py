"""GPU widget — utilization bars, clocks, power, temperature, roofline analysis."""

from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Label, ProgressBar, Static
from textual.widget import Widget

from visage.util import HistoryBuffer, format_bytes, render_sparkline


def _mini_bar(pct: float, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    filled = max(0, min(filled, width))
    empty = width - filled
    if pct >= 70:
        color = "green"
    elif pct >= 40:
        color = "yellow"
    else:
        color = "red"
    bar = "\u2588" * filled + "\u2591" * empty
    return f"[{color}]{bar}[/]"


class GpuWidget(Widget):
    available: bool = reactive(False)
    vendor: str = reactive("")
    name: str = reactive("")
    sm_util: float = reactive(0.0)
    mem_util: float = reactive(0.0)
    power_w: float = reactive(0.0)
    power_max_w: float = reactive(0.0)
    clock_core_mhz: float = reactive(0.0)
    clock_mem_mhz: float = reactive(0.0)
    temp_c: float = reactive(0.0)
    mem_used: int = reactive(0)
    mem_total: int = reactive(0)
    gflops_achieved: float = reactive(0.0)
    gflops_peak_fp32: float = reactive(0.0)
    gflops_peak_fp16: float = reactive(0.0)
    gbw_achieved: float = reactive(0.0)
    gbw_theoretical: float = reactive(0.0)
    arith_intensity: float = reactive(0.0)
    ridge_point: float = reactive(0.0)
    bound_by: str = reactive("")

    pcie_tx: float = reactive(0.0)
    pcie_rx: float = reactive(0.0)
    gpu_count: int = reactive(1)
    active_gpu_idx: int = reactive(0)

    def __init__(self):
        super().__init__()
        self._sm_hist = HistoryBuffer(60)
        self._mem_hist = HistoryBuffer(60)
        self._pwr_hist = HistoryBuffer(60)
        self._gpus_data: list[dict] = []
        self._th = {
            "sm_util": {"red": 80, "yellow": 50},
            "mem_util": {"red": 80, "yellow": 50},
            "temp_c": {"red": 85, "yellow": 70},
            "power_w": {"red": 90, "yellow": 75},
        }

    _THRESHOLD_KEY_MAP = {
        "gpu_sm_util": "sm_util",
        "gpu_mem_util": "mem_util",
        "gpu_temp_c": "temp_c",
        "gpu_power_w": "power_w",
    }

    def set_thresholds(self, t: dict) -> None:
        for key, value in t.items():
            mapped = self._THRESHOLD_KEY_MAP.get(key, key)
            if mapped not in self._th or not isinstance(value, dict):
                continue
            self._th[mapped] = {**self._th[mapped], **value}

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("GPU", id="gpu-title", classes="metric-title")
            with Horizontal(classes="metric-bar-row"):
                yield ProgressBar(id="gpu-sm-bar", total=100, show_eta=False, show_percentage=False)
                yield Static(id="gpu-sm-pct", classes="metric-value")
            with Horizontal(classes="metric-bar-row"):
                yield ProgressBar(id="gpu-mem-bar", total=100, show_eta=False, show_percentage=False)
                yield Static(id="gpu-mem-pct", classes="metric-value")
            yield Static(id="gpu-sparklines", classes="metric-detail")
            yield Static(id="gpu-power-temp", classes="metric-detail")
            yield Static(id="gpu-clocks", classes="metric-detail")
            yield Static(id="gpu-memory", classes="metric-detail")
            yield Static(id="gpu-pcie", classes="metric-detail")
            yield Static(id="gpu-roofline", classes="metric-detail")
            yield Static(id="gpu-bound", classes="metric-detail")

    def on_mount(self) -> None:
        self._title = self.query_one("#gpu-title", Label)
        self._sm_bar = self.query_one("#gpu-sm-bar", ProgressBar)
        self._sm_pct = self.query_one("#gpu-sm-pct", Static)
        self._mem_bar = self.query_one("#gpu-mem-bar", ProgressBar)
        self._mem_pct = self.query_one("#gpu-mem-pct", Static)
        self._sparklines = self.query_one("#gpu-sparklines", Static)
        self._power_temp = self.query_one("#gpu-power-temp", Static)
        self._clocks = self.query_one("#gpu-clocks", Static)
        self._memory = self.query_one("#gpu-memory", Static)
        self._pcie = self.query_one("#gpu-pcie", Static)
        self._roofline = self.query_one("#gpu-roofline", Static)
        self._bound = self.query_one("#gpu-bound", Static)

    def _color_temp(self, t: float) -> str:
        th = self._th["temp_c"]
        if t >= th["red"]:
            return f"[red]{t:.0f}\u00b0C[/]"
        if t >= th["yellow"]:
            return f"[yellow]{t:.0f}\u00b0C[/]"
        return f"[green]{t:.0f}\u00b0C[/]"

    def watch_available(self, val: bool) -> None:
        if not hasattr(self, "_title"):
            return
        if not val:
            self._title.update("GPU [dim]— no GPU detected (pip install visage[gpu])[/]")
            self._sm_bar.progress = 0
            self._sm_pct.update("")
            self._mem_bar.progress = 0
            self._mem_pct.update("")
            self._sparklines.update("")
            self._power_temp.update("")
            self._clocks.update("")
            self._memory.update("")
            self._pcie.update("")
            self._roofline.update("")
            self._bound.update("")
            for w in (
                self._sm_bar, self._mem_bar,
                self._sparklines, self._power_temp, self._clocks,
                self._memory, self._pcie, self._roofline, self._bound,
            ):
                w.display = False

    def watch_name(self, name: str) -> None:
        self._refresh_title()

    def _refresh_title(self) -> None:
        if not hasattr(self, "_title"):
            return
        vtag = {"nvidia": "[blue]NVIDIA[/]", "amd": "[red]AMD[/]"}.get(self.vendor, "")
        gpu_badge = f" [bold cyan][GPU {self.active_gpu_idx + 1}/{self.gpu_count}][/]" if self.gpu_count > 1 else ""
        self._title.update(f"GPU {vtag}{gpu_badge}  —  {self.name}")

    def watch_sm_util(self, val: float) -> None:
        if not hasattr(self, "_sm_bar"):
            return
        self._sm_bar.progress = min(val, 100.0)
        t = self._th["sm_util"]
        color = "green" if val < t["yellow"] else ("yellow" if val < t["red"] else "red")
        self._sm_pct.update(f"[{color}]{val:.0f}%[/]")

    def watch_mem_util(self, val: float) -> None:
        if not hasattr(self, "_mem_bar"):
            return
        self._mem_bar.progress = min(val, 100.0)
        t = self._th["mem_util"]
        color = "green" if val < t["yellow"] else ("yellow" if val < t["red"] else "red")
        self._mem_pct.update(f"[{color}]{val:.0f}%[/]")

    def watch_power_w(self, _: float) -> None:
        self._refresh_power_temp()

    def watch_power_max_w(self, _: float) -> None:
        self._refresh_power_temp()

    def watch_temp_c(self, _: float) -> None:
        self._refresh_power_temp()

    def _refresh_power_temp(self) -> None:
        if not self.available or not hasattr(self, "_power_temp"):
            return
        pct = (self.power_w / self.power_max_w * 100) if self.power_max_w > 0 else 0
        th = self._th["power_w"]
        if pct >= th["red"]:
            color = "red"
        elif pct >= th["yellow"]:
            color = "yellow"
        else:
            color = "green"
        self._power_temp.update(
            f"Power: {self.power_w:.0f}W / {self.power_max_w:.0f}W  [{color}]{pct:.0f}%[/]  "
            f"Temp: {self._color_temp(self.temp_c)}"
        )

    def watch_clock_core_mhz(self, _: float) -> None:
        self._refresh_clocks()

    def watch_clock_mem_mhz(self, _: float) -> None:
        self._refresh_clocks()

    def _refresh_clocks(self) -> None:
        if not self.available or not hasattr(self, "_clocks"):
            return
        self._clocks.update(
            f"Core: [bold]{self.clock_core_mhz:.0f}[/] MHz  "
            f"Mem: [bold]{self.clock_mem_mhz:.0f}[/] MHz"
        )

    def watch_mem_used(self, _: int) -> None:
        self._refresh_memory()

    def watch_mem_total(self, _: int) -> None:
        self._refresh_memory()

    def _refresh_memory(self) -> None:
        if not self.available or not hasattr(self, "_memory"):
            return
        pct = (self.mem_used / self.mem_total * 100) if self.mem_total > 0 else 0
        pct_str = _mini_bar(pct, 8)
        self._memory.update(
            f"Mem: {format_bytes(self.mem_used)} / {format_bytes(self.mem_total)}  {pct_str}"
        )
        if self.pcie_tx > 0 or self.pcie_rx > 0:
            from visage.util import format_rate
            self._pcie.update(f"PCIe: \u2191 {format_rate(self.pcie_tx)}  \u2193 {format_rate(self.pcie_rx)}")
        else:
            self._pcie.update("")

    def watch_gflops_achieved(self, _: float) -> None:
        self._refresh_roofline()

    def watch_gflops_peak_fp32(self, _: float) -> None:
        self._refresh_roofline()

    def watch_gflops_peak_fp16(self, _: float) -> None:
        self._refresh_roofline()

    def watch_gbw_achieved(self, _: float) -> None:
        self._refresh_roofline()

    def watch_gbw_theoretical(self, _: float) -> None:
        self._refresh_roofline()

    def watch_arith_intensity(self, _: float) -> None:
        self._refresh_roofline()

    def watch_ridge_point(self, _: float) -> None:
        self._refresh_roofline()

    def watch_bound_by(self, _: str) -> None:
        self._refresh_roofline()

    def _refresh_roofline(self) -> None:
        if not self.available or not hasattr(self, "_roofline"):
            return
        lines: list[str] = []

        fp32_pct = (self.gflops_achieved / self.gflops_peak_fp32 * 100) if self.gflops_peak_fp32 > 0 else 0
        lines.append(
            f"GFLOPS:  [bold]{self.gflops_achieved:.1f}[/] / {self.gflops_peak_fp32:.0f} FP32  "
            f"({fp32_pct:.0f}% {_mini_bar(fp32_pct, 8)})"
        )

        fp16_pct = (self.gflops_achieved / self.gflops_peak_fp16 * 100) if self.gflops_peak_fp16 > 0 else 0
        lines.append(
            f"         [bold]{self.gflops_achieved:.1f}[/] / {self.gflops_peak_fp16:.0f} FP16  "
            f"({fp16_pct:.0f}% {_mini_bar(fp16_pct, 8)})"
        )

        bw_pct = (self.gbw_achieved / self.gbw_theoretical * 100) if self.gbw_theoretical > 0 else 0
        lines.append(
            f"BW:      [bold]{self.gbw_achieved:.0f}[/] / {self.gbw_theoretical:.0f} GB/s  "
            f"({bw_pct:.0f}% {_mini_bar(bw_pct, 8)})"
        )

        lines.append(f"Intensity: [bold]{self.arith_intensity:.1f}[/] FLOP/byte")
        lines.append(f"Ridge:     [bold]{self.ridge_point:.1f}[/] FLOP/byte")

        lines.append("[dim]  \u2191 utilization-based estimate[/]")

        self._roofline.update("\n".join(lines))

        bound = self.bound_by
        if bound == "Compute":
            tag = f"[green]{bound}[/]  \u2190 above ridge, kernel is compute-limited"
        elif bound == "Memory":
            tag = f"[yellow]{bound}[/]  \u2190 below ridge, kernel is bandwidth-limited"
        else:
            tag = "[dim]Idle[/]"
        self._bound.update(f"Bound by: {tag}")

    def _refresh_sparklines(self) -> None:
        if not hasattr(self, "_sparklines"):
            return
        sm_spark = render_sparkline(self._sm_hist.normalize_pct(), 15)
        mem_spark = render_sparkline(self._mem_hist.normalize_pct(), 15)
        pwr_spark = render_sparkline(self._pwr_hist.normalize_pct(), 15)
        parts = []
        if sm_spark:
            parts.append(f"SM: {sm_spark}")
        if mem_spark:
            parts.append(f"Mem: {mem_spark}")
        if pwr_spark:
            parts.append(f"Pwr: {pwr_spark}")
        if parts:
            self._sparklines.update("  ".join(parts))
        else:
            self._sparklines.update("")

    def cycle_gpu(self) -> None:
        """Cycle to the next GPU when multiple are detected."""
        if self.gpu_count > 1:
            self.active_gpu_idx = (self.active_gpu_idx + 1) % self.gpu_count
            if self._gpus_data and self.active_gpu_idx < len(self._gpus_data):
                self._apply_gpu_data(self._gpus_data[self.active_gpu_idx])

    def _apply_gpu_data(self, cur: dict) -> None:
        self.vendor = cur.get("vendor", "")
        self.name = cur.get("name", "")
        self.sm_util = cur.get("sm_util", 0.0)
        self.mem_util = cur.get("mem_util", 0.0)
        self.power_w = cur.get("power_w", 0.0)
        self.power_max_w = cur.get("power_max_w", 0.0)
        self.clock_core_mhz = float(cur.get("clock_core_mhz", 0))
        self.clock_mem_mhz = float(cur.get("clock_mem_mhz", 0))
        self.temp_c = cur.get("temp_c", 0.0)
        self.mem_used = cur.get("mem_used_bytes", 0)
        self.mem_total = cur.get("mem_total_bytes", 0)
        self.pcie_tx = float(cur.get("pcie_tx_bytes_sec", 0.0))
        self.pcie_rx = float(cur.get("pcie_rx_bytes_sec", 0.0))
        self.gflops_achieved = cur.get("gflops_achieved", 0.0)
        self.gflops_peak_fp32 = cur.get("gflops_peak_fp32", 0.0)
        self.gflops_peak_fp16 = cur.get("gflops_peak_fp16", 0.0)
        self.gbw_achieved = cur.get("gbw_achieved", 0.0)
        self.gbw_theoretical = cur.get("gbw_theoretical", 0.0)
        self.arith_intensity = cur.get("arith_intensity", 0.0)
        self.ridge_point = cur.get("ridge_point", 0.0)
        self.bound_by = cur.get("bound_by", "")
        self._refresh_title()
        self._refresh_sparklines()

    def update_data(self, data: dict) -> None:
        self.available = data.get("available", False)
        if not self.available:
            return
        if hasattr(self, "_sm_bar"):
            for w in (
                self._sm_bar, self._mem_bar,
                self._sparklines, self._power_temp, self._clocks,
                self._memory, self._pcie, self._roofline, self._bound,
            ):
                w.display = True

        gpus = data.get("gpus", [])
        if gpus:
            self._gpus_data = gpus
            self.gpu_count = len(gpus)
            if self.active_gpu_idx >= len(gpus):
                self.active_gpu_idx = 0
            cur = gpus[self.active_gpu_idx]
        else:
            self._gpus_data = [data]
            self.gpu_count = data.get("gpu_count", 1)
            cur = data

        self._sm_hist.push(cur.get("sm_util", 0.0))
        self._mem_hist.push(cur.get("mem_util", 0.0))
        self._pwr_hist.push(cur.get("power_w", 0.0))
        self._apply_gpu_data(cur)

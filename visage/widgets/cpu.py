"""CPU usage widget — progress bar, percentage, per-core breakdown."""

from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Label, ProgressBar, Static
from textual.widget import Widget

from visage.util import format_percent


class CpuWidget(Widget):
    percent: float = reactive(0.0)
    per_cpu: list[float] = reactive([])

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("CPU", classes="metric-title")
            with Horizontal(classes="metric-bar-row"):
                yield ProgressBar(
                    id="cpu-bar",
                    total=100,
                    show_eta=False,
                    show_percentage=False,
                )
                yield Static(id="cpu-pct", classes="metric-value")
            yield Static(id="cpu-detail", classes="metric-detail")

    def watch_percent(self, value: float) -> None:
        self.query_one("#cpu-bar", ProgressBar).progress = min(value, 100.0)
        self.query_one("#cpu-pct", Static).update(format_percent(value))

    def watch_per_cpu(self, cores: list[float]) -> None:
        parts = []
        for i, p in enumerate(cores):
            label = f"C{i}:{p:.0f}%"
            if p >= 80:
                parts.append(f"[red]{label}[/]")
            elif p >= 50:
                parts.append(f"[yellow]{label}[/]")
            else:
                parts.append(f"[green]{label}[/]")
        detail = "  ".join(parts) if parts else ""
        self.query_one("#cpu-detail", Static).update(detail)

    def update_data(self, data: dict) -> None:
        self.percent = data["percent"]
        self.per_cpu = data.get("per_cpu", [])

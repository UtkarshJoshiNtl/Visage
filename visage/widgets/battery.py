"""Battery widget — charge level and status."""

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Label, Static
from textual.widget import Widget


def _battery_bar(pct: int, width: int = 12) -> str:
    if pct < 0:
        return "[dim]N/A[/]"
    filled = round(pct / 100 * width)
    filled = max(0, min(filled, width))
    empty = width - filled
    if pct <= 15:
        color = "red"
    elif pct <= 30:
        color = "yellow"
    else:
        color = "green"
    bar = "\u2588" * filled + "\u2591" * empty
    return f"[{color}]{bar}[/{color}]"


_STATUS_ICONS = {
    "Charging": "\u2191",
    "Discharging": "\u2193",
    "Full": "\u2713",
    "Not charging": "\u2022",
}


class BatteryWidget(Widget):
    available: bool = reactive(False)

    def __init__(self):
        super().__init__()

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("Battery", id="bat-title", classes="metric-title")
            yield Static(id="bat-content", classes="metric-detail")

    def on_mount(self) -> None:
        self._content = self.query_one("#bat-content", Static)

    def update_data(self, data: dict) -> None:
        available = data.get("available", False)
        if not available:
            self.display = False
            return
        self.display = True

        batteries = data.get("batteries", [])
        if not batteries:
            self.display = False
            return

        lines: list[str] = []
        for bat in batteries:
            name = bat.get("name", "BAT0")
            capacity = bat.get("capacity", -1)
            status = bat.get("status", "Unknown")
            icon = _STATUS_ICONS.get(status, "?")

            bar = _battery_bar(capacity)
            lines.append(f"  {icon} {bar} {capacity}%  [dim]{status}[/]")

        self._content.update("\n".join(lines))

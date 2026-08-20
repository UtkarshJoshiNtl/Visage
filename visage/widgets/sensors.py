"""Temperature, fan, and power sensors widget."""

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Label, Static
from textual.widget import Widget


def _color_temp(t: float) -> str:
    if t >= 85:
        return f"[red]{t:.0f}\u00b0C[/]"
    if t >= 70:
        return f"[yellow]{t:.0f}\u00b0C[/]"
    if t > 0:
        return f"[green]{t:.0f}\u00b0C[/]"
    return f"{t:.0f}\u00b0C"


def _color_power(w: float, max_w: float) -> str:
    if max_w <= 0:
        return f"{w:.1f}W"
    pct = w / max_w * 100
    if pct >= 90:
        return f"[red]{w:.1f}W / {max_w:.0f}W ({pct:.0f}%)[/]"
    if pct >= 70:
        return f"[yellow]{w:.1f}W / {max_w:.0f}W ({pct:.0f}%)[/]"
    return f"[green]{w:.1f}W / {max_w:.0f}W ({pct:.0f}%)[/]"


class SensorsWidget(Widget):
    available: bool = reactive(False)
    temp_data: list[dict] = reactive([])
    power_data: list[dict] = reactive([])

    def __init__(self):
        super().__init__()

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("Sensors", classes="metric-title")
            yield Static(id="sensors-content", classes="metric-detail")

    def on_mount(self) -> None:
        self._content = self.query_one("#sensors-content", Static)

    def update_data(self, data: dict) -> None:
        lines: list[str] = []

        temps = data.get("temperatures", {})
        temp_entries = temps.get("entries", []) if isinstance(temps, dict) else []
        if temp_entries:
            temp_parts = []
            for entry in temp_entries[:6]:
                label = entry.get("label", "")
                current = entry.get("current", 0.0)
                if current > 0:
                    temp_parts.append(f"{label}: {_color_temp(current)}")
            if temp_parts:
                lines.append("  ".join(temp_parts))

        fans = data.get("fans", {})
        fan_entries = fans.get("entries", []) if isinstance(fans, dict) else []
        if fan_entries:
            fan_parts = []
            for entry in fan_entries[:4]:
                label = entry.get("label", "fan")
                rpm = entry.get("rpm", 0)
                if rpm > 0:
                    fan_parts.append(f"{label}: {rpm} RPM")
            if fan_parts:
                lines.append("  ".join(fan_parts))

        power = data.get("power", {})
        power_entries = power.get("entries", []) if isinstance(power, dict) else []
        if power_entries:
            for entry in power_entries[:4]:
                name = entry.get("name", "package")
                energy = entry.get("energy_uj", 0)
                max_energy = entry.get("max_energy_uj", 0)
                if energy > 0:
                    if max_energy > 0:
                        lines.append(f"  {name}: {_color_power(energy / 1_000_000, max_energy / 1_000_000)}")
                    else:
                        lines.append(f"  {name}: {energy / 1_000_000:.1f}W")

        if lines:
            self._content.update("\n".join(lines))
        else:
            self._content.update("[dim]  No sensor data available[/]")

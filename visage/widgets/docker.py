"""Docker container widget — shows running container stats."""

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Label, Static
from textual.widget import Widget


class DockerWidget(Widget):
    available: bool = reactive(False)

    def __init__(self):
        super().__init__()

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("Docker", classes="metric-title")
            yield Static(id="docker-content", classes="metric-detail")

    def on_mount(self) -> None:
        self._content = self.query_one("#docker-content", Static)

    def update_data(self, data: dict) -> None:
        available = data.get("available", False)
        if not available:
            self.display = False
            return
        self.display = True

        containers = data.get("containers", [])
        if not containers:
            self._content.update("[dim]  No running containers[/]")
            return

        lines: list[str] = []
        for c in containers[:10]:
            name = c.get("name", "?")
            if len(name) > 16:
                name = name[:15] + "\u2026"
            cpu = c.get("cpu_pct", 0)
            mem_pct = c.get("mem_pct", 0)
            mem_usage = c.get("mem_usage", "")
            net = c.get("net_io", "")

            cpu_color = "red" if cpu >= 80 else ("yellow" if cpu >= 50 else "green")
            mem_color = "red" if mem_pct >= 80 else ("yellow" if mem_pct >= 50 else "green")

            lines.append(
                f"  [bold]{name:16s}[/] "
                f"CPU: [{cpu_color}]{cpu:5.1f}%[/]  "
                f"Mem: [{mem_color}]{mem_pct:5.1f}%[/]  "
                f"{mem_usage}"
            )

        self._content.update("\n".join(lines))

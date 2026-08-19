"""Process table widget — sortable, filterable, tree view with detail panel."""

import time
from typing import Any

from rich.table import Table
from textual import work
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Input, Label, Static
from textual.widget import Widget

from visage.collectors.process import collect, get_signal_choices, send_signal


def _fmt_time(ts: float) -> str:
    if ts <= 0:
        return ""
    elapsed = time.time() - ts
    days = int(elapsed // 86400)
    hours = int((elapsed % 86400) // 3600)
    mins = int((elapsed % 3600) // 60)
    if days > 0:
        return f"{days}d{hours}h"
    if hours > 0:
        return f"{hours}h{mins}m"
    return f"{mins}m"


def _fmt_rss(b: int) -> str:
    if b >= 1_073_741_824:
        return f"{b / 1_073_741_824:.1f}G"
    if b >= 1_048_576:
        return f"{b / 1_048_576:.0f}M"
    if b >= 1024:
        return f"{b / 1024:.0f}K"
    return str(b)


class ProcessesWidget(Widget):
    processes: list[dict[str, Any]] = reactive([])

    SORT_LABELS = {
        "cpu": "CPU%",
        "memory": "MEM%",
        "pid": "PID",
        "name": "NAME",
    }

    def __init__(self):
        super().__init__()
        self._sort_by = "cpu"
        self._sort_reverse = True
        self._filter_str = ""
        self._tree_mode = False
        self._selected_idx = 0
        self._show_detail = False
        self._show_filter = False
        self._show_signal = False
        self._signal_pid = 0
        self._detail_data: dict[str, Any] | None = None

    def compose(self):
        with Vertical(classes="metric-card"):
            yield Label("Processes", id="proc-title", classes="metric-title")
            yield Static(id="proc-banner", classes="metric-detail")
            yield Static(id="proc-table", classes="metric-detail")
            yield Static(id="proc-detail", classes="metric-detail")
            yield Input(placeholder="Filter processes...", id="proc-filter")
            yield Static(id="proc-signal", classes="metric-detail")

    def on_mount(self) -> None:
        self._banner = self.query_one("#proc-banner", Static)
        self._table = self.query_one("#proc-table", Static)
        self._detail = self.query_one("#proc-detail", Static)
        self._filter_input = self.query_one("#proc-filter", Input)
        self._signal_label = self.query_one("#proc-signal", Static)
        self._filter_input.display = False
        self._signal_label.display = False
        self._refresh_banner()

    def _refresh_banner(self) -> None:
        sort_label = self.SORT_LABELS.get(self._sort_by, "CPU%")
        rev = "\u25bc" if self._sort_reverse else "\u25b2"
        parts = [f"[bold]Sort:[/] {rev}{sort_label} [dim]s[/]"]
        if self._tree_mode:
            parts.append("[bold]Tree[/]")
        if self._filter_str:
            parts.append(f"[bold]Filter:[/] {self._filter_str}")
        parts.append("[dim]/search  x:signal  t:tree  enter:detail[/]")
        self._banner.update("  ".join(parts))

    def on_key(self, event) -> None:
        if self._show_filter:
            if event.key == "escape":
                self._show_filter = False
                self._filter_input.display = False
                event.stop()
            return

        if self._show_signal:
            choices = get_signal_choices()
            if event.key == "escape":
                self._show_signal = False
                self._signal_label.display = False
                self._signal_label.update("")
                event.stop()
                return
            try:
                idx = int(event.key) - 1
                if 0 <= idx < len(choices):
                    name, sig = choices[idx]
                    ok = send_signal(self._signal_pid, sig)
                    if ok:
                        self.notify(f"Sent {name} to PID {self._signal_pid}", timeout=3)
                    else:
                        self.notify(f"Failed: {name} to PID {self._signal_pid}", timeout=3, severity="error")
                    self._show_signal = False
                    self._signal_label.display = False
                    self._signal_label.update("")
                    event.stop()
            except (ValueError, TypeError):
                pass
            return

        procs = self.processes
        if not procs:
            return

        if event.key == "up":
            if self._selected_idx > 0:
                self._selected_idx -= 1
                self._refresh_table()
                event.stop()
        elif event.key == "down":
            if self._selected_idx < len(procs) - 1:
                self._selected_idx += 1
                self._refresh_table()
                event.stop()
        elif event.key == "s":
            self._cycle_sort()
            event.stop()
        elif event.key == "t":
            self._tree_mode = not self._tree_mode
            self._selected_idx = 0
            self._refresh_banner()
            self._refetch()
            event.stop()
        elif event.key == "slash":
            self._show_filter = True
            self._filter_input.display = True
            self._filter_input.focus()
            event.stop()
        elif event.key == "escape":
            if self._show_detail:
                self._show_detail = False
                self._detail.update("")
                event.stop()
        elif event.key == "enter":
            self._toggle_detail()
            event.stop()
        elif event.key == "x":
            if self._selected_idx < len(procs):
                pid = procs[self._selected_idx].get("pid", 0)
                if pid > 0:
                    self._show_signal_picker(pid)
                    event.stop()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "proc-filter":
            self._filter_str = event.value.strip()
            self._show_filter = False
            self._filter_input.display = False
            self._selected_idx = 0
            self._refresh_banner()
            self._refetch()

    def _cycle_sort(self) -> None:
        order = ["cpu", "memory", "pid", "name"]
        idx = order.index(self._sort_by) if self._sort_by in order else 0
        if self._sort_reverse:
            self._sort_reverse = False
        else:
            idx = (idx + 1) % len(order)
            self._sort_by = order[idx]
            self._sort_reverse = self._sort_by in ("cpu", "memory")
        self._selected_idx = 0
        self._refresh_banner()
        self._refetch()

    def _toggle_detail(self) -> None:
        procs = self.processes
        if not procs or self._selected_idx >= len(procs):
            return
        if self._show_detail:
            self._show_detail = False
            self._detail.update("")
        else:
            self._show_detail = True
            self._detail_data = procs[self._selected_idx]
            self._refresh_detail()

    def _refresh_detail(self) -> None:
        p = self._detail_data
        if not p:
            return
        lines = [
            f"[bold]PID:[/] {p.get('pid', '?')}  [bold]PPID:[/] {p.get('ppid', '?')}",
            f"[bold]User:[/] {p.get('username', '?')}  [bold]Status:[/] {p.get('status', '?')}",
            f"[bold]Nice:[/] {p.get('nice', 0)}  [bold]Threads:[/] {p.get('threads', 0)}",
            f"[bold]RSS:[/] {_fmt_rss(p.get('mem_rss', 0))}  [bold]Started:[/] {_fmt_time(p.get('start_time', 0))}",
        ]
        cmdline = p.get("cmdline", "")
        if cmdline and cmdline != p.get("name", ""):
            if len(cmdline) > 80:
                cmdline = cmdline[:79] + "\u2026"
            lines.append(f"[bold]Cmd:[/] {cmdline}")
        self._detail.update("\n".join(lines))

    def _show_signal_picker(self, pid: int) -> None:
        self._show_signal = True
        self._signal_pid = pid
        choices = get_signal_choices()
        sigs = "  ".join(f"[{i + 1}]{name}" for i, (name, _) in enumerate(choices))
        self._signal_label.display = True
        self._signal_label.update(f"[bold]Send signal to PID {pid}:[/]  {sigs}")

    def _refetch(self) -> None:
        self._do_fetch(self._sort_by, self._sort_reverse, self._filter_str, self._tree_mode)

    @work(thread=True, exclusive=True, group="proc-manual")
    def _do_fetch(self, sort_by, sort_reverse, filter_str, tree_mode) -> None:
        data = collect(
            top_n=30,
            sort_by=sort_by,
            sort_reverse=sort_reverse,
            filter_str=filter_str,
            tree_mode=tree_mode,
        )
        self.call_from_thread(self._set_data, data)

    def _set_data(self, data: list) -> None:
        self.processes = data

    def watch_processes(self, procs: list[dict[str, Any]]) -> None:
        if self._selected_idx >= len(procs):
            self._selected_idx = max(0, len(procs) - 1)
        self._refresh_table()
        if self._show_detail and self._detail_data:
            for p in procs:
                if p.get("pid") == self._detail_data.get("pid"):
                    self._detail_data = p
                    self._refresh_detail()
                    break

    def _refresh_table(self) -> None:
        procs = self.processes
        table = Table(box=None, padding=(0, 1), show_header=True, show_edge=False)
        table.add_column("", width=1)
        table.add_column("Name", no_wrap=True, style="bold", ratio=3)
        table.add_column("PID", justify="right", ratio=1)
        table.add_column("CPU%", justify="right", style="yellow", ratio=1)
        table.add_column("Mem%", justify="right", style="cyan", ratio=1)
        table.add_column("RSS", justify="right", style="dim", ratio=1)
        table.add_column("Thr", justify="right", style="dim", ratio=1)
        table.add_column("Time", justify="right", style="dim", ratio=1)

        for i, p in enumerate(procs):
            marker = "\u25b6" if i == self._selected_idx else " "
            name = p.get("name", "")
            depth = p.get("depth", 0)
            prefix = p.get("tree_prefix", "")
            if self._tree_mode and depth > 0:
                name = prefix + name
            elif self._tree_mode and depth == 0:
                name = "\u2500\u2500 " + name
            if len(name) > 32:
                name = name[:31] + "\u2026"

            elapsed = _fmt_time(p.get("start_time", 0))
            rss = _fmt_rss(p.get("mem_rss", 0))

            if i == self._selected_idx:
                table.add_row(
                    marker, f"[reverse]{name}[/]", str(p.get("pid", "")),
                    f"{p.get('cpu', 0):.1f}", f"{p.get('memory', 0):.1f}",
                    rss, str(p.get("threads", "")), elapsed,
                )
            else:
                table.add_row(
                    marker, name, str(p.get("pid", "")),
                    f"{p.get('cpu', 0):.1f}", f"{p.get('memory', 0):.1f}",
                    rss, str(p.get("threads", "")), elapsed,
                )

        if not procs:
            table.add_row("", "(no matching processes)", "", "", "", "", "", "")

        self._table.update(table)

    def update_data(self, data: list[dict[str, Any]]) -> None:
        self.processes = data

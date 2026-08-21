"""Process table widget — sortable, filterable, tree view with detail panel."""

import time
from typing import Any

from rich.table import Table
from textual import work
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from textual.widget import Widget

from visage.collectors.diagnostics import collect_process_diagnostics
from visage.collectors.process import collect, get_signal_choices, send_signal


class ProcessInspectModal(ModalScreen):
    """Deep-dive interactive diagnostic modal for a process."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
        ("1", "tab_overview", "Overview"),
        ("2", "tab_fds", "FDs"),
        ("3", "tab_sockets", "Sockets"),
        ("4", "tab_threads", "Threads"),
        ("5", "tab_env", "Env"),
    ]

    current_tab: int = reactive(1)

    def __init__(self, pid: int, proc_name: str = ""):
        super().__init__()
        self.pid = pid
        self.proc_name = proc_name
        self.diag = collect_process_diagnostics(pid)

    def compose(self):
        with Container(classes="inspect-modal-container"):
            with Vertical():
                yield Label(f"Process Diagnostics: PID {self.pid} — {self.proc_name or self.diag.get('name', '')}", id="modal-title")
                with Horizontal(id="modal-tabs-bar"):
                    yield Button("[1] Overview", id="btn-tab-1", variant="primary")
                    yield Button("[2] FDs", id="btn-tab-2")
                    yield Button("[3] Sockets", id="btn-tab-3")
                    yield Button("[4] Threads", id="btn-tab-4")
                    yield Button("[5] Env", id="btn-tab-5")
                with VerticalScroll(id="modal-body-scroll"):
                    yield Static(id="modal-content")
                yield Label("[dim]Keys: [1-5] switch view  |  [Esc/q] close[/]", id="modal-footer")

    def on_mount(self) -> None:
        self._content = self.query_one("#modal-content", Static)
        self._render_tab()

    def action_dismiss(self) -> None:
        self.app.pop_screen()

    def action_tab_overview(self) -> None:
        self.current_tab = 1
        self._render_tab()

    def action_tab_fds(self) -> None:
        self.current_tab = 2
        self._render_tab()

    def action_tab_sockets(self) -> None:
        self.current_tab = 3
        self._render_tab()

    def action_tab_threads(self) -> None:
        self.current_tab = 4
        self._render_tab()

    def action_tab_env(self) -> None:
        self.current_tab = 5
        self._render_tab()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-tab-1":
            self.action_tab_overview()
        elif btn_id == "btn-tab-2":
            self.action_tab_fds()
        elif btn_id == "btn-tab-3":
            self.action_tab_sockets()
        elif btn_id == "btn-tab-4":
            self.action_tab_threads()
        elif btn_id == "btn-tab-5":
            self.action_tab_env()

    def _render_tab(self) -> None:
        if not hasattr(self, "_content"):
            return
        d = self.diag
        lines = []

        if self.current_tab == 1:
            # Overview & Memory
            lines.append(f"[bold cyan]Process Overview & Silicon/Memory State[/]")
            lines.append(f"  [bold]PID:[/] {d.get('pid')}  [bold]PPID:[/] {d.get('ppid')}  [bold]Name:[/] {d.get('name')}")
            cmd = " ".join(d.get("cmdline", [])) or "(none)"
            lines.append(f"  [bold]Command:[/] {cmd}")
            lines.append("")
            lines.append("[bold yellow]Memory Footprint (/proc/[pid]/status):[/]")
            mem = d.get("memory", {})
            if mem:
                for k, v in mem.items():
                    lines.append(f"  \u2022 [bold]{k}:[/] {v}")
            else:
                lines.append("  (no memory info accessible)")
            lines.append("")
            lines.append("[bold green]I/O Statistics (/proc/[pid]/io):[/]")
            io_data = d.get("io", {})
            if io_data:
                for k, v in io_data.items():
                    lines.append(f"  \u2022 [bold]{k}:[/] {v}")
            else:
                lines.append("  (no IO stats accessible)")

        elif self.current_tab == 2:
            # File Descriptors
            fds = d.get("file_descriptors", [])
            lines.append(f"[bold cyan]Open File Descriptors ({len(fds)} total):[/]\n")
            if fds:
                table = Table(box=None, show_header=True, padding=(0, 1))
                table.add_column("FD", justify="right", style="cyan")
                table.add_column("Type", style="yellow")
                table.add_column("Resolved Target Path / Endpoint", style="white")
                for item in fds[:100]:
                    table.add_row(item["fd"], item["type"], item["target"])
                self._content.update(table)
                return
            else:
                lines.append("  (no file descriptors accessible or permission denied)")

        elif self.current_tab == 3:
            # Network Sockets
            sockets = d.get("sockets", [])
            lines.append(f"[bold cyan]Active Network Sockets ({len(sockets)} open):[/]\n")
            if sockets:
                table = Table(box=None, show_header=True, padding=(0, 1))
                table.add_column("Proto", style="cyan")
                table.add_column("Local Address", style="green")
                table.add_column("Remote Address", style="yellow")
                table.add_column("State", style="magenta")
                table.add_column("TX/RX Queue", style="dim")
                for s in sockets:
                    q = f"{s.get('tx_queue', 0)} / {s.get('rx_queue', 0)}"
                    table.add_row(s.get("proto", "tcp"), s.get("local_addr", ""), s.get("remote_addr", ""), s.get("state", ""), q)
                self._content.update(table)
                return
            else:
                lines.append("  (no open network sockets detected for this process)")

        elif self.current_tab == 4:
            # Threads
            threads = d.get("threads", [])
            lines.append(f"[bold cyan]Thread Breakdown ({len(threads)} active threads):[/]\n")
            if threads:
                table = Table(box=None, show_header=True, padding=(0, 1))
                table.add_column("TID", justify="right", style="cyan")
                table.add_column("Thread Name", style="white")
                table.add_column("State", style="green")
                for t in threads:
                    table.add_row(str(t["tid"]), t["name"], t["state"])
                self._content.update(table)
                return
            else:
                lines.append("  (no thread list accessible)")

        elif self.current_tab == 5:
            # Environment
            env = d.get("environ", {})
            lines.append(f"[bold cyan]Environment Variables ({len(env)} total):[/]\n")
            if env:
                for k, v in sorted(env.items()):
                    lines.append(f"  [bold green]{k}[/] = [white]{v}[/]")
            else:
                lines.append("  (environment inaccessible or empty)")

        self._content.update("\n".join(lines))


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
        self._aggregate_mode = False
        self._selected_idx = 0
        self._show_detail = False
        self._show_filter = False
        self._show_signal = False
        self._show_renice = False
        self._signal_pid = 0
        self._renice_pid = 0
        self._detail_data: dict[str, Any] | None = None
        self._vim_mode = False
        self._vim_pending: str = ""
        self._long_cmdline = False

    @property
    def sort_by(self) -> str:
        return self._sort_by

    @property
    def sort_reverse(self) -> bool:
        return self._sort_reverse

    @property
    def filter_str(self) -> str:
        return self._filter_str

    @property
    def tree_mode(self) -> bool:
        return self._tree_mode

    @property
    def aggregate_mode(self) -> bool:
        return self._aggregate_mode

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
        if not hasattr(self, "_banner"):
            return
        sort_label = self.SORT_LABELS.get(self._sort_by, "CPU%")
        rev = "\u25bc" if self._sort_reverse else "\u25b2"
        parts = [f"[bold]Sort:[/] {rev}{sort_label} [dim]s[/]"]
        if self._tree_mode:
            parts.append("[bold]Tree[/]")
        if self._aggregate_mode:
            parts.append("[bold]Agg[/]")
        if self._long_cmdline:
            parts.append("[bold]Long[/]")
        if self._vim_mode:
            parts.append("[bold]VIM[/]")
        if self._filter_str:
            parts.append(f"[bold]Filter:[/] {self._filter_str}")
        parts.append("[dim]/search  x:signal  i:inspect  t:tree  a:agg  v:vim  l:long  n:nice  enter:detail[/]")
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

        if self._show_renice:
            if event.key == "escape":
                self._show_renice = False
                self._signal_label.display = False
                self._signal_label.update("")
                event.stop()
                return
            try:
                val = int(event.key)
                if 0 <= val <= 9:
                    self._apply_renice(self._renice_pid, val)
                    self._show_renice = False
                    self._signal_label.display = False
                    self._signal_label.update("")
                    event.stop()
            except (ValueError, TypeError):
                pass
            return

        procs = self.processes
        if not procs:
            return

        if self._vim_mode:
            self._handle_vim_key(event)
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
        elif event.key == "pageup":
            self._selected_idx = max(0, self._selected_idx - 10)
            self._refresh_table()
            event.stop()
        elif event.key == "pagedown":
            self._selected_idx = min(len(procs) - 1, self._selected_idx + 10)
            self._refresh_table()
            event.stop()
        elif event.key == "s":
            self._cycle_sort()
            event.stop()
        elif event.key == "t":
            self._tree_mode = not self._tree_mode
            self._aggregate_mode = False
            self._selected_idx = 0
            self._refresh_banner()
            self._refetch()
            event.stop()
        elif event.key == "a":
            self._aggregate_mode = not self._aggregate_mode
            self._tree_mode = False
            self._selected_idx = 0
            self._refresh_banner()
            self._refetch()
            event.stop()
        elif event.key == "l":
            self._long_cmdline = not self._long_cmdline
            self._refresh_table()
            self._refresh_banner()
            event.stop()
        elif event.key == "i":
            if self._selected_idx < len(procs):
                p = procs[self._selected_idx]
                pid = p.get("pid", 0)
                if pid > 0:
                    try:
                        self.app.push_screen(ProcessInspectModal(pid, p.get("name", "")))
                    except Exception as e:
                        self.notify(f"Inspect failed: {e}", severity="error")
                    event.stop()
        elif event.key == "n":
            if self._selected_idx < len(procs):
                pid = procs[self._selected_idx].get("pid", 0)
                if pid > 0:
                    self._show_renice_picker(pid)
                    event.stop()
        elif event.key == "v":
            self._vim_mode = True
            self._vim_pending = ""
            self._refresh_banner()
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

    def _handle_vim_key(self, event) -> None:
        procs = self.processes
        key = event.key

        if key == "escape":
            self._vim_mode = False
            self._vim_pending = ""
            self._refresh_banner()
            event.stop()
            return

        if key in ("j", "down"):
            if self._selected_idx < len(procs) - 1:
                self._selected_idx += 1
                self._refresh_table()
            event.stop()
        elif key in ("k", "up"):
            if self._selected_idx > 0:
                self._selected_idx -= 1
                self._refresh_table()
            event.stop()
        elif key == "g":
            if self._vim_pending == "g":
                self._selected_idx = 0
                self._refresh_table()
                self._vim_pending = ""
            else:
                self._vim_pending = "g"
        elif key == "G":
            self._selected_idx = max(0, len(procs) - 1)
            self._refresh_table()
            self._vim_pending = ""
        elif key in ("h", "left"):
            self._selected_idx = max(0, self._selected_idx - 5)
            self._refresh_table()
            event.stop()
        elif key in ("l", "right"):
            self._selected_idx = min(len(procs) - 1, self._selected_idx + 5)
            self._refresh_table()
            event.stop()
        else:
            self._vim_pending = ""

    def _show_renice_picker(self, pid: int) -> None:
        self._show_renice = True
        self._renice_pid = pid
        self._signal_label.display = True
        self._signal_label.update(f"[bold]Set nice value for PID {pid} (0-9):[/]")

    def _apply_renice(self, pid: int, nice_val: int) -> None:
        import os
        try:
            os.setpriority(os.PRIO_PROCESS, pid, nice_val)
            self.notify(f"Set nice={nice_val} for PID {pid}", timeout=3)
        except (OSError, PermissionError) as e:
            self.notify(f"Renice failed: {e}", timeout=3, severity="error")

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
        io_read = p.get("io_read", 0)
        io_write = p.get("io_write", 0)
        if io_read or io_write:
            from visage.util import format_bytes
            lines.append(f"[bold]I/O:[/] R:{format_bytes(io_read)} W:{format_bytes(io_write)}")
        cmdline = p.get("cmdline", "")
        if cmdline and cmdline != p.get("name", ""):
            if len(cmdline) > 80:
                cmdline = cmdline[:79] + "\u2026"
            lines.append(f"[bold]Cmd:[/] {cmdline}")
        ai_fw = p.get("ai_framework")
        if ai_fw:
            lines.append(f"[bold magenta]AI Framework:[/] [bold]{ai_fw}[/]")
        self._detail.update("\n".join(lines))

    def _show_signal_picker(self, pid: int) -> None:
        self._show_signal = True
        self._signal_pid = pid
        choices = get_signal_choices()
        sigs = "  ".join(f"[{i + 1}]{name}" for i, (name, _) in enumerate(choices))
        self._signal_label.display = True
        self._signal_label.update(f"[bold]Send signal to PID {pid}:[/]  {sigs}")

    def _refetch(self) -> None:
        self._do_fetch(self._sort_by, self._sort_reverse, self._filter_str, self._tree_mode, self._aggregate_mode)

    @work(thread=True, exclusive=True, group="proc-manual")
    def _do_fetch(self, sort_by, sort_reverse, filter_str, tree_mode, aggregate_mode) -> None:
        data = collect(
            top_n=30,
            sort_by=sort_by,
            sort_reverse=sort_reverse,
            filter_str=filter_str,
            tree_mode=tree_mode,
            aggregate_mode=aggregate_mode,
        )
        self.call_from_thread(self._set_data, data)

    def _set_data(self, data: list) -> None:
        self.processes = data

    def watch_processes(self, procs: list[dict[str, Any]]) -> None:
        if self._selected_idx >= len(procs):
            self._selected_idx = max(0, len(procs) - 1)
        if not hasattr(self, "_table"):
            return
        self._refresh_table()
        if self._show_detail and self._detail_data:
            for p in procs:
                if p.get("pid") == self._detail_data.get("pid"):
                    self._detail_data = p
                    self._refresh_detail()
                    break

    def _refresh_table(self) -> None:
        if not hasattr(self, "_table"):
            return
        procs = self.processes
        table = Table(box=None, padding=(0, 1), show_header=True, show_edge=False)
        table.add_column("", width=1)
        table.add_column("Name", no_wrap=True, style="bold", ratio=3)
        table.add_column("PID", justify="right", ratio=1)
        table.add_column("CPU%", justify="right", style="yellow", ratio=1)
        table.add_column("Mem%", justify="right", style="cyan", ratio=1)
        table.add_column("RSS", justify="right", style="dim", ratio=1)
        table.add_column("Thr", justify="right", style="dim", ratio=1)
        table.add_column("Nice", justify="right", style="dim", ratio=1)
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

            cmdline = p.get("cmdline", "")
            if self._long_cmdline and cmdline and cmdline != name:
                if len(cmdline) > 48:
                    cmdline = cmdline[:47] + "\u2026"
                name = cmdline

            ai_fw = p.get("ai_framework")
            ai_tag = f" [magenta][{ai_fw}][/]" if ai_fw else ""

            elapsed = _fmt_time(p.get("start_time", 0))
            rss = _fmt_rss(p.get("mem_rss", 0))
            nice = p.get("nice", 0)
            count = p.get("count", 0)
            pid_str = str(p.get("pid", ""))
            if count > 1:
                pid_str = f"({count})"

            if i == self._selected_idx:
                table.add_row(
                    marker, f"[reverse]{name}{ai_tag}[/]", pid_str,
                    f"{p.get('cpu', 0):.1f}", f"{p.get('memory', 0):.1f}",
                    rss, str(p.get("threads", "")), str(nice), elapsed,
                )
            else:
                table.add_row(
                    marker, f"{name}{ai_tag}", pid_str,
                    f"{p.get('cpu', 0):.1f}", f"{p.get('memory', 0):.1f}",
                    rss, str(p.get("threads", "")), str(nice), elapsed,
                )

        if not procs:
            table.add_row("", "(no matching processes)", "", "", "", "", "", "", "")

        self._table.update(table)

    def update_data(self, data: list[dict[str, Any]]) -> None:
        self.processes = data

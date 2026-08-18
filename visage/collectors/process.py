"""Process metric collector — rich process data with sort, filter, and tree support."""

import os
import signal as signal_mod
import sys
from typing import Any

import psutil


_SORT_KEYS = {
    "cpu": lambda p: p.get("cpu", 0.0),
    "memory": lambda p: p.get("memory", 0.0),
    "pid": lambda p: p.get("pid", 0),
    "name": lambda p: p.get("name", "").lower(),
}


def _collect_one(proc: psutil.Process) -> dict[str, Any] | None:
    try:
        info = proc.as_dict(
            attrs=["pid", "ppid", "name", "username", "cpu_percent",
                    "memory_percent", "memory_info", "status", "nice",
                    "num_threads", "create_time", "cmdline"]
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None

    name = info.get("name", "")
    if not name:
        return None

    mem_info = info.get("memory_info")
    mem_rss = mem_info.rss if mem_info else 0

    cmdline = info.get("cmdline")
    cmdline_str = " ".join(cmdline) if cmdline else name

    return {
        "pid": info.get("pid", 0),
        "ppid": info.get("ppid", 0),
        "name": name,
        "username": info.get("username", "") or "",
        "cpu": info.get("cpu_percent", 0.0) or 0.0,
        "memory": info.get("memory_percent", 0.0) or 0.0,
        "mem_rss": mem_rss,
        "status": info.get("status", ""),
        "nice": info.get("nice", 0),
        "threads": info.get("num_threads", 0),
        "start_time": info.get("create_time", 0.0),
        "cmdline": cmdline_str,
    }


def collect(
    top_n: int = 20,
    sort_by: str = "cpu",
    sort_reverse: bool = True,
    filter_str: str = "",
    tree_mode: bool = False,
) -> list[dict[str, Any]]:
    processes: list[dict[str, Any]] = []

    for proc in psutil.process_iter():
        data = _collect_one(proc)
        if data is None:
            continue
        if filter_str:
            flt = filter_str.lower()
            if (flt not in data["name"].lower()
                    and flt not in data["cmdline"].lower()
                    and flt not in data["username"].lower()):
                continue
        processes.append(data)

    if tree_mode:
        return _build_tree(processes, top_n)

    sort_fn = _SORT_KEYS.get(sort_by, _SORT_KEYS["cpu"])
    processes.sort(key=sort_fn, reverse=sort_reverse)
    return processes[:top_n]


def _build_tree(processes: list[dict], top_n: int) -> list[dict]:
    by_pid = {p["pid"]: p for p in processes}
    children: dict[int, list[dict]] = {}
    roots: list[dict] = []

    for p in processes:
        ppid = p["ppid"]
        if ppid in by_pid:
            children.setdefault(ppid, []).append(p)
        else:
            roots.append(p)

    sort_fn = _SORT_KEYS["cpu"]
    roots.sort(key=sort_fn, reverse=True)

    result: list[dict] = []

    def walk(node: dict, depth: int, is_last: bool, prefix: str) -> None:
        if len(result) >= top_n:
            return
        node["depth"] = depth
        node["is_last"] = is_last
        node["tree_prefix"] = prefix
        result.append(node)
        kids = children.get(node["pid"], [])
        kids.sort(key=sort_fn, reverse=True)
        for i, child in enumerate(kids):
            if i < len(kids) - 1:
                child_prefix = prefix + "\u251c\u2500\u2500 "
                walk(child, depth + 1, False, child_prefix)
            else:
                child_prefix = prefix + "\u2514\u2500\u2500 "
                walk(child, depth + 1, True, child_prefix)

    for i, root in enumerate(roots):
        if len(result) >= top_n:
            break
        if i < len(roots) - 1:
            walk(root, 0, False, "\u251c\u2500\u2500 ")
        else:
            walk(root, 0, True, "\u2514\u2500\u2500 ")

    return result[:top_n]


def send_signal(pid: int, sig: int) -> bool:
    try:
        os.kill(pid, sig)
        return True
    except (OSError, ProcessLookupError, PermissionError):
        return False


def get_signal_choices() -> list[tuple[str, int]]:
    choices = [
        ("SIGTERM", signal_mod.SIGTERM),
        ("SIGKILL", signal_mod.SIGKILL),
        ("SIGSTOP", signal_mod.SIGSTOP),
        ("SIGCONT", signal_mod.SIGCONT),
        ("SIGHUP", signal_mod.SIGHUP),
        ("SIGUSR1", signal_mod.SIGUSR1),
        ("SIGUSR2", signal_mod.SIGUSR2),
        ("SIGINT", signal_mod.SIGINT),
    ]
    return choices

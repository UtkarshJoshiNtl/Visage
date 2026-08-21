"""Developer Diagnostics collector — file descriptors, sockets, threads, and memory maps."""

import os
import sys
from pathlib import Path
from typing import Any

from visage.collectors.network import get_process_sockets


def _mask_sensitive(key: str, val: str) -> str:
    lower_k = key.lower()
    if any(secret in lower_k for secret in ("token", "key", "secret", "password", "auth", "credential")):
        if len(val) > 8:
            return val[:3] + "..." + val[-3:]
        return "********"
    return val


def collect_process_diagnostics(pid: int) -> dict[str, Any]:
    """Collect deep diagnostic telemetry for a specific process ID.

    Returns open FDs, network sockets, thread breakdown, memory statistics,
    and sanitized environment variables.
    """
    result: dict[str, Any] = {
        "pid": pid,
        "available": False,
        "name": "",
        "ppid": 0,
        "cmdline": [],
        "environ": {},
        "memory": {},
        "io": {},
        "threads": [],
        "file_descriptors": [],
        "sockets": [],
        "error": None,
    }

    if sys.platform != "linux":
        result["error"] = "Process diagnostics only available on Linux"
        return result

    proc_dir = Path(f"/proc/{pid}")
    if not proc_dir.exists():
        result["error"] = f"PID {pid} not found"
        return result

    result["available"] = True

    # 1. Read /proc/[pid]/status
    try:
        with open(proc_dir / "status") as f:
            status_text = f.read()
        for line in status_text.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip()
                if k == "Name":
                    result["name"] = v
                elif k == "PPid":
                    result["ppid"] = int(v) if v.isdigit() else 0
                elif k in ("VmPeak", "VmSize", "VmHWM", "VmRSS", "VmSwap", "Threads",
                           "voluntary_ctxt_switches", "nonvoluntary_ctxt_switches", "Cpus_allowed_list"):
                    result["memory"][k] = v
    except (OSError, PermissionError) as e:
        result["error"] = str(e)

    # 2. Read /proc/[pid]/cmdline
    try:
        with open(proc_dir / "cmdline", "rb") as f:
            raw_cmd = f.read()
        if isinstance(raw_cmd, str):
            raw_cmd = raw_cmd.encode("utf-8", errors="replace")
        args = [arg.decode("utf-8", errors="replace") for arg in raw_cmd.split(b"\x00") if arg]
        result["cmdline"] = args
    except (OSError, PermissionError):
        pass

    # 3. Read /proc/[pid]/environ (sanitized)
    try:
        with open(proc_dir / "environ", "rb") as f:
            raw_env = f.read()
        if isinstance(raw_env, str):
            raw_env = raw_env.encode("utf-8", errors="replace")
        for item in raw_env.split(b"\x00"):
            if b"=" in item:
                k, v = item.split(b"=", 1)
                key_str = k.decode("utf-8", errors="replace")
                val_str = v.decode("utf-8", errors="replace")
                result["environ"][key_str] = _mask_sensitive(key_str, val_str)
    except (OSError, PermissionError):
        pass

    # 4. Read /proc/[pid]/io
    try:
        with open(proc_dir / "io") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    if v.isdigit():
                        result["io"][k] = int(v)
    except (OSError, PermissionError):
        pass

    # 5. Open File Descriptors (/proc/[pid]/fd)
    fd_dir = proc_dir / "fd"
    fds: list[dict[str, Any]] = []
    try:
        for entry in os.listdir(fd_dir):
            try:
                target = os.readlink(str(fd_dir / entry))
                fd_type = "File"
                if target.startswith("socket:["):
                    fd_type = "Socket"
                elif target.startswith("pipe:["):
                    fd_type = "Pipe"
                elif target.startswith("anon_inode:"):
                    fd_type = "AnonInode"
                elif target.startswith("/dev/"):
                    fd_type = "Device"
                fds.append({
                    "fd": entry,
                    "type": fd_type,
                    "target": target,
                })
            except (OSError, PermissionError):
                fds.append({"fd": entry, "type": "Unknown", "target": "(permission denied)"})
    except (OSError, PermissionError):
        pass

    fds.sort(key=lambda x: int(x["fd"]) if x["fd"].isdigit() else 999999)
    result["file_descriptors"] = fds

    # 6. Active network sockets
    try:
        result["sockets"] = get_process_sockets(pid)
    except Exception:
        pass

    # 7. Threads (/proc/[pid]/task)
    task_dir = proc_dir / "task"
    threads: list[dict[str, Any]] = []
    try:
        for tid in os.listdir(task_dir):
            tid_path = task_dir / tid
            t_name = "?"
            t_state = "?"
            try:
                with open(tid_path / "comm") as f:
                    t_name = f.read().strip()
            except (OSError, PermissionError):
                pass
            try:
                with open(tid_path / "stat") as f:
                    stat_parts = f.read().split()
                    if len(stat_parts) >= 3:
                        t_state = stat_parts[2]
            except (OSError, PermissionError):
                pass

            threads.append({
                "tid": int(tid) if tid.isdigit() else 0,
                "name": t_name,
                "state": t_state,
            })
    except (OSError, PermissionError):
        pass

    threads.sort(key=lambda x: x["tid"])
    result["threads"] = threads

    return result

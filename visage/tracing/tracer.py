"""Process tracer — eBPF-driven process birth/death monitoring.

Uses kernel tracepoints (sched_process_exec / sched_process_exit) via BCC
to capture process lifecycle events at the instant they occur, bypassing
the /proc polling tax entirely. Falls back to /proc-based polling when
BCC is not available.
"""

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BPF_PROGRAM = r"""
#include <uapi/linux/ptrace.h>

struct process_event {
    u32 pid;
    char comm[16];
    u8 is_exit;
};

BPF_RINGBUF(events, 262144);

TRACEPOINT_PROBE(sched, sched_process_exec) {
    struct process_event *e = bpf_ringbuf_reserve(&events, sizeof(struct process_event), 0);
    if (!e) return 0;

    e->pid = args->pid;
    bpf_get_current_comm(e->comm, sizeof(e->comm));
    e->is_exit = 0;

    bpf_ringbuf_submit(e, 0);
    return 0;
}

TRACEPOINT_PROBE(sched, sched_process_exit) {
    struct process_event *e = bpf_ringbuf_reserve(&events, sizeof(struct process_event), 0);
    if (!e) return 0;

    e->pid = args->pid;
    bpf_get_current_comm(e->comm, sizeof(e->comm));
    e->is_exit = 1;

    bpf_ringbuf_submit(e, 0);
    return 0;
}
"""


def _read_proc_info(pid: int) -> dict:
    try:
        with open(f"/proc/{pid}/status") as f:
            text = f.read()
        name = "?"
        state = "?"
        ppid = 0
        for line in text.splitlines():
            if line.startswith("Name:"):
                name = line.split(maxsplit=1)[1]
            elif line.startswith("State:"):
                state = line.split(maxsplit=1)[1]
            elif line.startswith("PPid:"):
                ppid = int(line.split()[1])
        return {"name": name, "state": state, "ppid": ppid}
    except (OSError, IOError):
        return {}


class EbpfTracer:
    """eBPF-based process lifecycle monitor via BCC.

    Hooks sched_process_exec and sched_process_exit tracepoints.
    Requires the ``python3-bpfcc`` system package and root / CAP_BPF.
    """

    def __init__(self) -> None:
        self._bpf = None
        self._events: list[dict[str, Any]] = []

    def start(self) -> None:
        from bcc import BPF

        self._bpf = BPF(text=BPF_PROGRAM)
        self._bpf["events"].open_ring_buffer(self._handle_event)

    def stop(self) -> None:
        if self._bpf is not None:
            self._bpf.cleanup()
            self._bpf = None

    def poll(self) -> list[dict[str, Any]]:
        self._events.clear()
        if self._bpf is not None:
            self._bpf.ring_buffer_consume()
        now = time.time()
        result = []
        for e in self._events:
            result.append({
                "time": now,
                "pid": e["pid"],
                "event": "exited" if e["is_exit"] else "new",
                "name": e["comm"],
                "state": "Z" if e["is_exit"] else "R",
            })
        return result

    def _handle_event(self, ctx: Any, data: bytes, size: int) -> None:
        event = self._bpf["events"].event(data)
        self._events.append({
            "pid": event.pid,
            "comm": event.comm.decode("utf-8", errors="replace").rstrip("\x00"),
            "is_exit": bool(event.is_exit),
        })

    @property
    def available(self) -> bool:
        return True


class ProcessTracer:
    """/proc-based process lifecycle monitor (fallback).

    Polls /proc for PID diffs. Slower and misses short-lived processes,
    but requires no special permissions or dependencies.
    """

    def __init__(self) -> None:
        self._known: set[int] = set()
        self._events: list[dict[str, Any]] = []

    def start(self) -> None:
        self._known = self._list_pids()

    def stop(self) -> None:
        pass

    def _list_pids(self) -> set[int]:
        try:
            return {int(p.name) for p in Path("/proc").iterdir() if p.name.isdigit()}
        except PermissionError:
            return set()

    def poll(self) -> list[dict[str, Any]]:
        current = self._list_pids()
        new_pids = current - self._known
        gone_pids = self._known - current
        events: list[dict[str, Any]] = []
        now = time.time()
        for pid in new_pids:
            info = _read_proc_info(pid)
            events.append({
                "time": now,
                "pid": pid,
                "event": "new",
                "name": info.get("name", "?"),
                "state": info.get("state", "R"),
            })
        for pid in gone_pids:
            events.append({
                "time": now,
                "pid": pid,
                "event": "exited",
                "name": "?",
                "state": "Z",
            })
        self._known = current
        self._events.extend(events)
        return events

    @property
    def available(self) -> bool:
        return True


def create_tracer() -> EbpfTracer | ProcessTracer:
    """Create the best available tracer.

    Tries eBPF first; falls back to /proc polling.
    Returns a started tracer instance or None if neither is available.
    """
    try:
        t = EbpfTracer()
        t.start()
        return t
    except Exception:
        pass

    try:
        t = ProcessTracer()
        t.start()
        return t
    except Exception:
        return None

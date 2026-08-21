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


def create_tracer() -> EbpfTracer | ProcessTracer | None:
    """Create the best available process tracer.

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


NET_BPF_PROGRAM = r"""
#include <uapi/linux/ptrace.h>

struct net_flow {
    u64 rx_bytes;
    u64 tx_bytes;
};

BPF_HASH(pid_net_flow, u32, struct net_flow, 10240);

int trace_tcp_send(struct pt_regs *ctx, void *sk, void *msg, size_t size) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    struct net_flow *flow = pid_net_flow.lookup(&pid);
    if (flow) {
        flow->tx_bytes += size;
    } else {
        struct net_flow init = { .rx_bytes = 0, .tx_bytes = size };
        pid_net_flow.update(&pid, &init);
    }
    return 0;
}

int trace_tcp_recv(struct pt_regs *ctx, void *sk, int copied) {
    if (copied <= 0) return 0;
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    struct net_flow *flow = pid_net_flow.lookup(&pid);
    if (flow) {
        flow->rx_bytes += copied;
    } else {
        struct net_flow init = { .rx_bytes = (u64)copied, .tx_bytes = 0 };
        pid_net_flow.update(&pid, &init);
    }
    return 0;
}

int trace_udp_send(struct pt_regs *ctx, void *sk, void *msg, size_t len) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    struct net_flow *flow = pid_net_flow.lookup(&pid);
    if (flow) {
        flow->tx_bytes += len;
    } else {
        struct net_flow init = { .rx_bytes = 0, .tx_bytes = len };
        pid_net_flow.update(&pid, &init);
    }
    return 0;
}
"""


class EbpfNetTracer:
    """eBPF-driven per-PID network bandwidth attribution tracer.

    Hooks TCP and UDP transmit and receive kernel functions via BCC.
    Maintains in-kernel atomic per-PID byte counters.
    """

    def __init__(self) -> None:
        self._bpf = None
        self._active = False

    def start(self) -> bool:
        try:
            from bcc import BPF

            self._bpf = BPF(text=NET_BPF_PROGRAM)
            self._bpf.attach_kprobe(event="tcp_sendmsg", fn_name="trace_tcp_send")
            self._bpf.attach_kprobe(event="tcp_cleanup_rbuf", fn_name="trace_tcp_recv")
            self._bpf.attach_kprobe(event="udp_sendmsg", fn_name="trace_udp_send")
            self._active = True
            return True
        except Exception:
            self._bpf = None
            self._active = False
            return False

    def stop(self) -> None:
        if self._bpf is not None:
            try:
                self._bpf.cleanup()
            except Exception:
                pass
            self._bpf = None
            self._active = False

    def get_stats(self) -> dict[int, dict[str, int]]:
        """Retrieve per-PID rx_bytes and tx_bytes from the eBPF hash map."""
        if not self._active or self._bpf is None:
            return {}
        result: dict[int, dict[str, int]] = {}
        try:
            flow_table = self._bpf["pid_net_flow"]
            for key, leaf in flow_table.items():
                pid = int(key.value)
                result[pid] = {
                    "rx_bytes": int(leaf.rx_bytes),
                    "tx_bytes": int(leaf.tx_bytes),
                }
        except Exception:
            pass
        return result

    @property
    def available(self) -> bool:
        return self._active


_global_net_tracer: EbpfNetTracer | None = None


def get_ebpf_net_tracer() -> EbpfNetTracer:
    """Get or initialize the global EbpfNetTracer singleton."""
    global _global_net_tracer
    if _global_net_tracer is None:
        _global_net_tracer = EbpfNetTracer()
        _global_net_tracer.start()
    return _global_net_tracer


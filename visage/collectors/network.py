"""Network I/O metric collector — per-interface breakdown and per-process approximation."""

import logging
import os
import sys
import threading
from typing import Any

import psutil


logger = logging.getLogger(__name__)

_lock = threading.Lock()
_prev_per_nic: dict[str, dict[str, float]] = {}
_prev_total: dict[str, float] = {}


def collect() -> dict[str, Any]:
    """Collect network I/O counters with delta-based rates."""
    global _prev_per_nic, _prev_total

    with _lock:
        total: dict[str, Any] = {}
        try:
            counters = psutil.net_io_counters()
            if counters:
                total = {
                    "bytes_sent": float(counters.bytes_sent),
                    "bytes_recv": float(counters.bytes_recv),
                    "packets_sent": float(counters.packets_sent),
                    "packets_recv": float(counters.packets_recv),
                }
        except Exception:
            logger.debug("net_io_counters failed", exc_info=True)

        pernic: dict[str, dict[str, Any]] = {}
        try:
            counters = psutil.net_io_counters(pernic=True)
            addrs = psutil.net_if_addrs()
            if counters:
                for name, c in counters.items():
                    if name == "lo":
                        continue
                    ip = ""
                    if name in addrs:
                        for a in addrs[name]:
                            if a.family.name in ("AF_INET", "AF_INET6"):
                                ip = a.address
                                break
                    pernic[name] = {
                        "bytes_sent": float(c.bytes_sent),
                        "bytes_recv": float(c.bytes_recv),
                        "packets_sent": float(c.packets_sent),
                        "packets_recv": float(c.packets_recv),
                        "ip": ip,
                    }
        except Exception:
            logger.debug("net_io_counters(pernic) failed", exc_info=True)

        return {
            "total": total,
            "pernic": pernic,
        }


TCP_STATES = {
    "01": "ESTABLISHED",
    "02": "SYN_SENT",
    "03": "SYN_RECV",
    "04": "FIN_WAIT1",
    "05": "FIN_WAIT2",
    "06": "TIME_WAIT",
    "07": "CLOSE",
    "08": "CLOSE_WAIT",
    "09": "LAST_ACK",
    "0A": "LISTEN",
    "0B": "CLOSING",
}


def _hex_to_ip_port(hex_str: str) -> tuple[str, int]:
    try:
        ip_hex, port_hex = hex_str.split(":")
        port = int(port_hex, 16)
        if len(ip_hex) == 8:
            # IPv4 (little-endian hex)
            octets = [str(int(ip_hex[i:i+2], 16)) for i in (6, 4, 2, 0)]
            ip = ".".join(octets)
        else:
            ip = ip_hex
        return ip, port
    except Exception:
        return "?", 0


def parse_socket_tables() -> dict[int, dict[str, Any]]:
    """Parse /proc/net/tcp, tcp6, udp, udp6 and map socket inode to details."""
    sockets: dict[int, dict[str, Any]] = {}
    if sys.platform != "linux":
        return sockets

    files = [
        ("/proc/net/tcp", "tcp"),
        ("/proc/net/tcp6", "tcp6"),
        ("/proc/net/udp", "udp"),
        ("/proc/net/udp6", "udp6"),
    ]

    for path, proto in files:
        try:
            with open(path) as f:
                lines = f.readlines()
            for line in lines[1:]:
                parts = line.strip().split()
                if len(parts) >= 10:
                    local_ip, local_port = _hex_to_ip_port(parts[1])
                    rem_ip, rem_port = _hex_to_ip_port(parts[2])
                    state = TCP_STATES.get(parts[3], parts[3]) if "tcp" in proto else "STATELESS"
                    tx_queue, rx_queue = 0, 0
                    if ":" in parts[4]:
                        q_parts = parts[4].split(":")
                        tx_queue = int(q_parts[0], 16)
                        rx_queue = int(q_parts[1], 16)
                    inode = int(parts[9])
                    # Prefer TCP metadata over UDP if inode collision
                    if inode not in sockets or "tcp" in proto:
                        sockets[inode] = {
                            "proto": proto,
                            "local_addr": f"{local_ip}:{local_port}",
                            "remote_addr": f"{rem_ip}:{rem_port}" if rem_port > 0 else "*:*",
                            "state": state,
                            "tx_queue": tx_queue,
                            "rx_queue": rx_queue,
                            "inode": inode,
                        }
        except (OSError, ValueError):
            continue

    return sockets


def get_process_socket_inodes(pid: int) -> list[int]:
    """Retrieve list of open socket inodes for a given PID."""
    inodes: list[int] = []
    if sys.platform != "linux":
        return inodes

    fd_dir = f"/proc/{pid}/fd"
    try:
        for entry in os.listdir(fd_dir):
            try:
                target = os.readlink(f"{fd_dir}/{entry}")
                if target.startswith("socket:["):
                    inode_str = target[8:-1]
                    if inode_str.isdigit():
                        inodes.append(int(inode_str))
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        pass

    return inodes


def get_process_sockets(pid: int) -> list[dict[str, Any]]:
    """Get active network sockets associated with a given PID."""
    inodes = set(get_process_socket_inodes(pid))
    if not inodes:
        return []

    socket_map = parse_socket_tables()
    matched = []
    for inode in inodes:
        if inode in socket_map:
            matched.append(socket_map[inode])
    return matched


def _netns_id(pid: int) -> str | None:
    """Return the inode of the process's network namespace, or None if unreadable."""
    try:
        target = os.readlink(f"/proc/{pid}/ns/net")
        return target.split("[")[-1].rstrip("]")
    except OSError:
        return None


def _read_proc_net_dev(pid: int) -> tuple[int, int]:
    """Read cumulative non-loopback rx/tx byte counters from a process's netns view."""
    rx_bytes = 0
    tx_bytes = 0
    try:
        with open(f"/proc/{pid}/net/dev") as f:
            lines = f.readlines()
        for line in lines[2:]:
            parts = line.split()
            if len(parts) >= 10:
                iface = parts[0].rstrip(":")
                if iface != "lo":
                    rx_bytes += int(parts[1])
                    tx_bytes += int(parts[9])
    except (OSError, ValueError):
        pass
    return rx_bytes, tx_bytes


def collect_per_process(top_n: int = 10) -> list[dict[str, Any]]:
    """Collect per-process network attribution with eBPF and socket accounting."""
    if sys.platform != "linux":
        return []

    # 1. Try eBPF tracer first
    try:
        from visage.tracing.tracer import get_ebpf_net_tracer

        tracer = get_ebpf_net_tracer()
        if tracer and tracer.available:
            ebpf_stats = tracer.get_stats()
            if ebpf_stats:
                results = []
                for p in psutil.process_iter(["pid", "name"]):
                    try:
                        pid = p.info["pid"]
                        if pid in ebpf_stats:
                            st = ebpf_stats[pid]
                            results.append({
                                "pid": pid,
                                "name": p.info.get("name", ""),
                                "rx_bytes": st.get("rx_bytes", 0),
                                "tx_bytes": st.get("tx_bytes", 0),
                                "rx_bytes_est": float(st.get("rx_bytes", 0)),
                                "tx_bytes_est": float(st.get("tx_bytes", 0)),
                                "method": "ebpf",
                            })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                if results:
                    results.sort(key=lambda x: x["rx_bytes"] + x["tx_bytes"], reverse=True)
                    return results[:top_n]
    except Exception:
        logger.debug("eBPF per-process attribution failed", exc_info=True)

    # 2. Inode-aware socket & namespace fallback.
    # /proc/<pid>/net/dev reports counters per network namespace, not per
    # process: summing it across processes multiplies traffic by the number
    # of processes sharing a namespace. Group processes by netns, read each
    # namespace's counters once, then attribute that namespace's traffic
    # across its members by CPU share so estimates sum to actual traffic.
    results: list[dict[str, Any]] = []
    try:
        socket_map = parse_socket_tables()
        procs: list[dict[str, Any]] = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                info = p.info
                pid = info["pid"]
                inodes = get_process_socket_inodes(pid)
                sockets = [socket_map[i] for i in inodes if i in socket_map]
                procs.append({
                    "pid": pid,
                    "name": info.get("name", ""),
                    "cpu": info.get("cpu_percent", 0.0) or 0.0,
                    "socket_count": len(sockets),
                    "sockets": sockets,
                    "netns": _netns_id(pid),
                })
            except (OSError, ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        ns_members: dict[str | None, list[dict[str, Any]]] = {}
        for proc in procs:
            ns_members.setdefault(proc["netns"], []).append(proc)

        for netns, members in ns_members.items():
            if netns is None:
                # Namespace unreadable (other user): cannot attribute honestly.
                for member in members:
                    member["rx_total"] = 0
                    member["tx_total"] = 0
                continue
            rx_total, tx_total = _read_proc_net_dev(members[0]["pid"])
            for member in members:
                member["rx_total"] = rx_total
                member["tx_total"] = tx_total

        for members in ns_members.values():
            total_cpu = sum(m["cpu"] for m in members)
            for m in members:
                share = (m["cpu"] / total_cpu) if total_cpu > 0 else (1.0 / len(members))
                rx_est = m["rx_total"] * share
                tx_est = m["tx_total"] * share
                results.append({
                    "pid": m["pid"],
                    "name": m["name"],
                    "rx_bytes": int(rx_est),
                    "tx_bytes": int(tx_est),
                    "rx_bytes_est": rx_est,
                    "tx_bytes_est": tx_est,
                    "socket_count": m["socket_count"],
                    "sockets": m["sockets"],
                    "cpu_share": m["cpu"],
                    "method": "socket_inode" if m["socket_count"] > 0 else "proc_net_dev",
                })

        results.sort(key=lambda x: x["rx_bytes_est"] + x["tx_bytes_est"] + (x["socket_count"] * 1024), reverse=True)
    except Exception:
        logger.debug("socket-inode per-process attribution failed", exc_info=True)

    return results[:top_n]

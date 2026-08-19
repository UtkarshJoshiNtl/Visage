"""Disk I/O metric collector — per-partition breakdown with usage stats."""

import sys
from typing import Any

import psutil


_VIRTUAL_FS_TYPES = frozenset((
    "proc", "sysfs", "devpts", "tmpfs", "cgroup", "cgroup2",
    "overlay", "squashfs", "devtmpfs", "securityfs", "pstore",
    "debugfs", "hugetlbfs", "mqueue", "autofs", "tracefs",
    "bpf", "fusectl", "configfs", "binfmt_misc", "nsfs",
    "rpc_pipefs", "nfsd", "fuse.gvfsd-fuse",
))


def _linux_disk_partitions() -> list[dict[str, Any]]:
    partitions = []
    try:
        with open("/proc/mounts") as f:
            mount_lines = f.readlines()
    except OSError:
        return partitions

    btrfs_roots: dict[str, str] = {}

    for line in mount_lines:
        parts = line.split()
        if len(parts) < 4:
            continue
        device, mount, fstype, opts = parts[0], parts[1], parts[2], parts[3]
        if not device.startswith("/"):
            continue
        if fstype in _VIRTUAL_FS_TYPES:
            continue
        if "noauto" in opts.split(","):
            continue

        if fstype == "btrfs":
            subvol = None
            for opt in opts.split(","):
                if opt.startswith("subvol="):
                    subvol = opt.split("=", 1)[1]
                    break
            if subvol and subvol != "/":
                if device in btrfs_roots:
                    continue
                btrfs_roots[device] = mount
            elif not subvol or subvol == "/":
                btrfs_roots[device] = mount

        try:
            usage = psutil.disk_usage(mount)
            partitions.append({
                "device": device,
                "mount": mount,
                "fstype": fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            })
        except (OSError, PermissionError, ValueError):
            continue
    return partitions


def collect() -> dict[str, Any]:
    perdisk = {}
    try:
        counters = psutil.disk_io_counters(perdisk=True)
        if counters:
            for name, c in counters.items():
                perdisk[name] = {
                    "read_bytes": float(c.read_bytes),
                    "write_bytes": float(c.write_bytes),
                    "read_count": float(c.read_count),
                    "write_count": float(c.write_count),
                }
    except Exception:
        pass

    total_counters = None
    try:
        total_counters = psutil.disk_io_counters()
    except Exception:
        pass

    total_stats = {}
    if total_counters:
        total_stats = {
            "read_bytes": float(total_counters.read_bytes),
            "write_bytes": float(total_counters.write_bytes),
            "read_count": float(total_counters.read_count),
            "write_count": float(total_counters.write_count),
        }

    partitions = []
    if sys.platform == "linux":
        partitions = _linux_disk_partitions()
    else:
        try:
            parts = psutil.disk_partitions(all=False)
            for p in parts:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    partitions.append({
                        "device": p.device,
                        "mount": p.mountpoint,
                        "fstype": p.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent,
                    })
                except (OSError, PermissionError):
                    continue
        except Exception:
            pass

    return {
        "total": total_stats,
        "perdisk": perdisk,
        "partitions": partitions,
    }

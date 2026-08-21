"""Data exporter — snapshot system metrics to CSV, JSON, or log files."""

import csv
import json
import time
from pathlib import Path
from typing import Any


def export_json(snapshot: dict[str, Any], path: str | Path, indent: int = 2) -> Path:
    """Write a JSON snapshot with timestamp."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"timestamp": time.time(), **snapshot}
    path.write_text(json.dumps(data, indent=indent, default=str))
    return path


def export_json_lines(path: str | Path, snapshot: dict[str, Any]) -> Path:
    """Append a JSON-lines entry (one JSON object per line)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"timestamp": time.time(), **snapshot}
    with open(path, "a") as f:
        f.write(json.dumps(data, default=str) + "\n")
    return path


def export_csv(
    rows: list[dict[str, Any]],
    path: str | Path,
    fieldnames: list[str] | None = None,
) -> Path:
    """Write rows as CSV. Appends if file already exists."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not fieldnames and rows:
        all_keys: set[str] = set()
        for row in rows:
            all_keys.update(row.keys())
        fieldnames = sorted(all_keys)
    mode = "a" if path.exists() else "w"
    with open(path, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or [])
        if mode == "w":
            writer.writeheader()
        writer.writerows(rows)
    return path


def export_log(
    message: str,
    path: str | Path,
) -> Path:
    """Append a timestamped log line."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    return path


def prometheus_format(metrics: dict[str, Any], prefix: str = "visage") -> str:
    """Convert a metrics dict to Prometheus exposition format."""
    lines: list[str] = []

    def _flatten(obj: Any, prefix_parts: list[str]) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                _flatten(v, prefix_parts + [k])
        elif isinstance(obj, (int, float)):
            name = "_".join(prefix_parts)
            name = name.replace(".", "_").replace("-", "_")
            lines.append(f"{prefix}_{name} {obj}")

    _flatten(metrics, [])
    return "\n".join(lines) + "\n" if lines else ""

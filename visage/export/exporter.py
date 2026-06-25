"""Data exporter — snapshot system metrics to CSV or JSON."""

import csv
import json
import time
from pathlib import Path
from typing import Any


def export_json(snapshot: dict[str, Any], path: str | Path) -> Path:
    """Write a JSON snapshot."""
    path = Path(path)
    data = {"timestamp": time.time(), **snapshot}
    path.write_text(json.dumps(data, indent=2, default=str))
    return path


def export_csv(
    rows: list[dict[str, Any]],
    path: str | Path,
    fieldnames: list[str] | None = None,
) -> Path:
    """Write rows as CSV. Appends if file already exists."""
    path = Path(path)
    if not fieldnames and rows:
        fieldnames = list(rows[0].keys())
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
    with open(path, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    return path

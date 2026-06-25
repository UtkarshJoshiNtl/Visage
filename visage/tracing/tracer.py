"""Process tracer — monitor process creation and termination events."""

import os
import time
from pathlib import Path
from typing import Any


class ProcessTracer:
    """Watch /proc for new processes and track their lifetimes."""

    def __init__(self) -> None:
        self._known: set[int] = set()
        self.events: list[dict[str, Any]] = []

    def poll(self) -> list[dict[str, Any]]:
        """Return new events since last poll."""
        current = self._list_pids()
        new_pids = current - self._known
        gone_pids = self._known - current
        events: list[dict[str, Any]] = []
        now = time.time()
        for pid in new_pids:
            info = self._read_proc(pid)
            events.append({
                "time": now,
                "pid": pid,
                "event": "new",
                "name": info.get("name", "?"),
                "state": info.get("state", "?"),
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
        self.events.extend(events)
        return events

    def _list_pids(self) -> set[int]:
        try:
            return {int(p.name) for p in Path("/proc").iterdir() if p.name.isdigit()}
        except PermissionError:
            return set()

    def _read_proc(self, pid: int) -> dict:
        try:
            with open(f"/proc/{pid}/status") as f:
                text = f.read()
            name = ""
            state = ""
            for line in text.splitlines():
                if line.startswith("Name:"):
                    name = line.split(maxsplit=1)[1]
                if line.startswith("State:"):
                    state = line.split(maxsplit=1)[1]
            return {"name": name, "state": state}
        except (OSError, IOError):
            return {}

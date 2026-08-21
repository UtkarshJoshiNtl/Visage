"""Remote monitoring server — exposes system metrics via FastAPI with WebSocket."""

import asyncio
import json
import logging
import os
import secrets
import time
from functools import partial

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from starlette.requests import Request

from visage.collectors import cpu, disk, memory, network, process, gpu
from visage.collectors.sensors import collect as collect_sensors
from visage.collectors.battery import collect as collect_battery
from visage.collectors.docker import collect as collect_docker
from visage.collectors.psi import collect as collect_psi

logger = logging.getLogger("visage.remote")

try:
    from visage import __version__ as _VERSION
except Exception:
    _VERSION = "unknown"

app = FastAPI(title="Visage Remote", version=_VERSION)

_DEFAULT_ORIGINS = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:8090",
    "http://127.0.0.1:8090",
]
_cors_origins = os.environ.get("VISAGE_CORS_ORIGINS", "").strip()
allow_origins = _cors_origins.split(",") if _cors_origins else _DEFAULT_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

_AUTH_TOKEN = os.environ.get("VISAGE_AUTH_TOKEN", "")
_semaphore = asyncio.Semaphore(4)

_CACHE_TTL_SECONDS = 1.0
_snapshot_lock = asyncio.Lock()
_snapshot: dict | None = None
_snapshot_at = 0.0


def _verify_token(request: Request) -> None:
    if not _AUTH_TOKEN:
        return
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and secrets.compare_digest(auth[7:], _AUTH_TOKEN):
        return
    raise HTTPException(status_code=401, detail="Invalid or missing auth token")


async def _run_collect(collector_fn, *args, **kwargs):
    return await asyncio.get_running_loop().run_in_executor(
        None, partial(collector_fn, *args, **kwargs)
    )


async def _collect_all() -> dict:
    async with _semaphore:
        cpu_data, mem_data, disk_data, net_data = await asyncio.gather(
            _run_collect(cpu.collect),
            _run_collect(memory.collect),
            _run_collect(disk.collect),
            _run_collect(network.collect),
        )
        proc_data, sensor_data, bat_data, gpu_data = await asyncio.gather(
            _run_collect(process.collect, top_n=20),
            _run_collect(collect_sensors),
            _run_collect(collect_battery),
            _run_collect(gpu.collect),
        )
        docker_data = await _run_collect(collect_docker)
        psi_data = await _run_collect(collect_psi)
    return {
        "cpu": cpu_data,
        "memory": mem_data,
        "disk": disk_data,
        "network": net_data,
        "gpu": gpu_data,
        "processes": proc_data,
        "sensors": sensor_data,
        "battery": bat_data,
        "docker": docker_data,
        "psi": psi_data,
    }


async def get_snapshot() -> dict:
    """Return a cached system snapshot, refreshing when older than the TTL.

    A single collection consumer keeps per-collector rate state (e.g. the
    jiffy deltas in cpu.py) consistent no matter how many clients poll —
    concurrent callers advancing shared collector state made CPU rates
    depend on whoever polled last. Callers must treat the returned dict
    as read-only.
    """
    global _snapshot, _snapshot_at
    async with _snapshot_lock:
        now = time.monotonic()
        if _snapshot is None or (now - _snapshot_at) >= _CACHE_TTL_SECONDS:
            _snapshot = await _collect_all()
            _snapshot_at = time.monotonic()
        return _snapshot


@app.get("/")
async def root():
    return {"service": "Visage Remote Monitoring", "version": _VERSION}


@app.get("/metrics", dependencies=[Depends(_verify_token)])
async def metrics():
    return await get_snapshot()


@app.get("/metrics/prometheus", dependencies=[Depends(_verify_token)])
async def prometheus_metrics():
    snap = await get_snapshot()
    cpu_data = snap["cpu"]
    mem_data = snap["memory"]
    disk_data = snap["disk"]
    net_data = snap["network"]
    gpu_data = snap["gpu"]
    from visage.export.exporter import prometheus_format
    flat = {
        "cpu_percent": cpu_data.get("percent", 0),
        "cpu_count": cpu_data.get("count", 0),
        "memory_percent": mem_data.get("percent", 0),
        "memory_used": mem_data.get("used", 0),
        "memory_total": mem_data.get("total", 0),
        "disk_read_bytes": disk_data.get("total", {}).get("read_bytes", 0),
        "disk_write_bytes": disk_data.get("total", {}).get("write_bytes", 0),
        "network_bytes_recv": net_data.get("total", {}).get("bytes_recv", 0),
        "network_bytes_sent": net_data.get("total", {}).get("bytes_sent", 0),
        "gpu_count": gpu_data.get("gpu_count", 1 if gpu_data.get("available") else 0),
        "gpu_sm_util": gpu_data.get("sm_util", 0),
        "gpu_temp_c": gpu_data.get("temp_c", 0),
    }
    for g in gpu_data.get("gpus", []):
        idx = g.get("index", 0)
        flat[f"gpu_{idx}_sm_util"] = g.get("sm_util", 0)
        flat[f"gpu_{idx}_mem_util"] = g.get("mem_util", 0)
        flat[f"gpu_{idx}_temp_c"] = g.get("temp_c", 0)
        flat[f"gpu_{idx}_power_w"] = g.get("power_w", 0)
        flat[f"gpu_{idx}_gflops_achieved"] = g.get("gflops_achieved", 0)
    return PlainTextResponse(prometheus_format(flat))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    await websocket.accept()

    if _AUTH_TOKEN:
        token = websocket.headers.get("authorization", "")
        if not (token.startswith("Bearer ") and secrets.compare_digest(token[7:], _AUTH_TOKEN)):
            await websocket.close(code=4001, reason="Unauthorized")
            return

    interval = 2.0
    try:
        while True:
            # Bound concurrent collections, not connections: holding the
            # semaphore across sleep/send would let a few idle clients
            # starve every HTTP endpoint.
            snap = await get_snapshot()
            data = {
                "timestamp": time.time(),
                "cpu": snap["cpu"],
                "memory": snap["memory"],
                "disk": snap["disk"],
                "network": snap["network"],
                "processes": snap["processes"],
            }
            await websocket.send_text(json.dumps(data, default=str))
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def serve(host: str = "127.0.0.1", port: int = 8090) -> None:
    """Start the remote monitoring server."""
    if host not in _LOOPBACK_HOSTS and not _AUTH_TOKEN:
        logger.warning(
            "Binding to %s without VISAGE_AUTH_TOKEN exposes process command "
            "lines, usernames, and hardware metrics to the network.",
            host,
        )
        print(
            f"WARNING: binding to {host} without VISAGE_AUTH_TOKEN exposes "
            "process command lines and usernames unauthenticated. "
            "Set VISAGE_AUTH_TOKEN or use --remote-host 127.0.0.1."
        )
    uvicorn.run(app, host=host, port=port)

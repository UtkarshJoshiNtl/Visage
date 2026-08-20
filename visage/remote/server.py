"""Remote monitoring server — exposes system metrics via FastAPI with WebSocket."""

import asyncio
import json
import logging
import time
from functools import partial

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from visage.collectors import cpu, disk, memory, network, process
from visage.collectors.sensors import collect as collect_sensors
from visage.collectors.battery import collect as collect_battery

logger = logging.getLogger("visage.remote")

app = FastAPI(title="Visage Remote", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _run_collect(collector_fn, *args, **kwargs):
    return await asyncio.get_event_loop().run_in_executor(
        None, partial(collector_fn, *args, **kwargs)
    )


@app.get("/")
async def root():
    return {"service": "Visage Remote Monitoring", "version": "0.3.0"}


@app.get("/metrics")
async def metrics():
    cpu_data, mem_data, disk_data, net_data = await asyncio.gather(
        _run_collect(cpu.collect),
        _run_collect(memory.collect),
        _run_collect(disk.collect),
        _run_collect(network.collect),
    )
    proc_data, sensor_data, bat_data = await asyncio.gather(
        _run_collect(process.collect, top_n=20),
        _run_collect(collect_sensors),
        _run_collect(collect_battery),
    )
    return {
        "cpu": cpu_data,
        "memory": mem_data,
        "disk": disk_data,
        "network": net_data,
        "processes": proc_data,
        "sensors": sensor_data,
        "battery": bat_data,
    }


@app.get("/metrics/prometheus")
async def prometheus_metrics():
    cpu_data, mem_data, disk_data, net_data = await asyncio.gather(
        _run_collect(cpu.collect),
        _run_collect(memory.collect),
        _run_collect(disk.collect),
        _run_collect(network.collect),
    )
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
    }
    return PlainTextResponse(prometheus_format(flat))


@app.get("/cpu")
async def cpu_metrics():
    return await _run_collect(cpu.collect)


@app.get("/memory")
async def mem_metrics():
    return await _run_collect(memory.collect)


@app.get("/disk")
async def disk_metrics():
    return await _run_collect(disk.collect)


@app.get("/network")
async def net_metrics():
    return await _run_collect(network.collect)


@app.get("/processes")
async def proc_metrics():
    return await _run_collect(process.collect, top_n=30)


@app.get("/gpu")
async def gpu_metrics():
    from visage.collectors.gpu import collect as collect_gpu
    return await _run_collect(collect_gpu)


@app.get("/sensors")
async def sensor_metrics():
    return await _run_collect(collect_sensors)


@app.get("/battery")
async def battery_metrics():
    return await _run_collect(collect_battery)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    await websocket.accept()
    interval = 2.0
    try:
        while True:
            cpu_data, mem_data, disk_data, net_data = await asyncio.gather(
                _run_collect(cpu.collect),
                _run_collect(memory.collect),
                _run_collect(disk.collect),
                _run_collect(network.collect),
            )
            proc_data = await _run_collect(process.collect, top_n=20)
            data = {
                "timestamp": time.time(),
                "cpu": cpu_data,
                "memory": mem_data,
                "disk": disk_data,
                "network": net_data,
                "processes": proc_data,
            }
            await websocket.send_text(json.dumps(data, default=str))
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")


def serve(host: str = "0.0.0.0", port: int = 8090) -> None:
    """Start the remote monitoring server."""
    uvicorn.run(app, host=host, port=port)

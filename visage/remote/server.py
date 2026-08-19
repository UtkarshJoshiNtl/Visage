"""Remote monitoring server — exposes system metrics via FastAPI with WebSocket."""

import asyncio
import json
import time

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from visage.collectors import cpu, disk, memory, network, process
from visage.collectors.sensors import collect as collect_sensors
from visage.collectors.battery import collect as collect_battery

app = FastAPI(title="Visage Remote", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"service": "Visage Remote Monitoring", "version": "0.2.0"}


@app.get("/metrics")
async def metrics():
    return {
        "cpu": cpu.collect(),
        "memory": memory.collect(),
        "disk": disk.collect(),
        "network": network.collect(),
        "processes": process.collect(top_n=20),
        "sensors": collect_sensors(),
        "battery": collect_battery(),
    }


@app.get("/cpu")
async def cpu_metrics():
    return cpu.collect()


@app.get("/memory")
async def mem_metrics():
    return memory.collect()


@app.get("/disk")
async def disk_metrics():
    return disk.collect()


@app.get("/network")
async def net_metrics():
    return network.collect()


@app.get("/processes")
async def proc_metrics():
    return process.collect(top_n=30)


@app.get("/gpu")
async def gpu_metrics():
    from visage.collectors.gpu import collect as collect_gpu
    return collect_gpu()


@app.get("/sensors")
async def sensor_metrics():
    return collect_sensors()


@app.get("/battery")
async def battery_metrics():
    return collect_battery()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    await websocket.accept()
    interval = 2.0
    try:
        while True:
            data = {
                "timestamp": time.time(),
                "cpu": cpu.collect(),
                "memory": memory.collect(),
                "disk": disk.collect(),
                "network": network.collect(),
                "processes": process.collect(top_n=20),
            }
            await websocket.send_text(json.dumps(data, default=str))
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


def serve(host: str = "0.0.0.0", port: int = 8090) -> None:
    """Start the remote monitoring server."""
    uvicorn.run(app, host=host, port=port)

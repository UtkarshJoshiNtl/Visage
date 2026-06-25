"""Remote monitoring server — exposes system metrics via FastAPI."""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from visage.collectors import cpu, disk, memory, network, process
from visage.collectors.sensors import collect as collect_sensors

app = FastAPI(title="Visage Remote", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"service": "Visage Remote Monitoring", "version": "0.1.0"}


@app.get("/metrics")
async def metrics():
    return {
        "cpu": cpu.collect(),
        "memory": memory.collect(),
        "disk": disk.collect(),
        "network": network.collect(),
        "processes": process.collect(),
        "sensors": collect_sensors(),
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


def serve(host: str = "0.0.0.0", port: int = 8090) -> None:
    """Start the remote monitoring server."""
    uvicorn.run(app, host=host, port=port)

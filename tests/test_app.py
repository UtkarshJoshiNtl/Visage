"""Smoke tests for the app — mount with disabled widgets must not crash."""

import json
import tempfile

import pytest
from textual.pilot import Pilot

from visage.app import VisageApp


@pytest.mark.asyncio
async def _run_app(cfg: dict, actions=None):
    actions = actions or []
    with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
        json.dump(cfg, f)
        f.flush()
        app = VisageApp(config_path=f.name)
    async with app.run_test() as pilot:
        await pilot.pause()
        for fn in actions:
            await fn(pilot)
        app.exit()


@pytest.mark.asyncio
async def test_full_dashboard_mounts():
    await _run_app({})


@pytest.mark.asyncio
async def test_only_cpu_enabled_mounts_without_crash():
    cfg = {
        "widgets": {
            "enabled": ["cpu"],
            "order": ["cpu", "gpu", "memory", "disk", "network", "processes"],
        },
    }
    await _run_app(cfg)


@pytest.mark.asyncio
async def test_gpu_disabled_mounts_without_crash():
    cfg = {"widgets": {"enabled": ["cpu", "memory", "disk", "network", "processes"]}}
    await _run_app(cfg)


@pytest.mark.asyncio
async def test_processes_disabled_mounts_without_crash():
    cfg = {"widgets": {"enabled": ["cpu", "memory", "disk", "network", "gpu"]}}
    await _run_app(cfg)


@pytest.mark.asyncio
async def test_refresh_cycle_after_mount():
    async def press_refresh(pilot: Pilot) -> None:
        await pilot.press("r")

    await _run_app({}, actions=[press_refresh])


@pytest.mark.asyncio
async def test_cycle_delay_after_mount():
    async def cycle(pilot: Pilot) -> None:
        await pilot.press("d")

    await _run_app({}, actions=[cycle])

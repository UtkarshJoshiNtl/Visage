"""Tests for the remote server snapshot cache and auth."""

import pytest

fastapi = pytest.importorskip("fastapi")

from unittest.mock import patch

from visage.remote import server


def _fake_snapshot(tag: str) -> dict:
    return {
        "cpu": {"percent": 1.0, "tag": tag},
        "memory": {},
        "disk": {"total": {}},
        "network": {"total": {}, "pernic": {}},
        "gpu": {},
        "processes": [],
        "sensors": {},
        "battery": {},
        "docker": {},
        "psi": {},
    }


class TestSnapshotCache:
    @pytest.mark.asyncio
    async def test_cache_hits_within_ttl(self):
        server._snapshot = None
        server._snapshot_at = 0.0
        calls = []

        async def fake_collect_all():
            calls.append(len(calls))
            return _fake_snapshot(f"v{len(calls)}")

        with patch.object(server, "_CACHE_TTL_SECONDS", 10.0), \
             patch.object(server, "_collect_all", side_effect=fake_collect_all):
            a = await server.get_snapshot()
            b = await server.get_snapshot()
            assert a is b
            assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_cache_refreshes_after_ttl(self):
        server._snapshot = None
        server._snapshot_at = 0.0
        calls = []

        async def fake_collect_all():
            calls.append(len(calls))
            return _fake_snapshot(f"v{len(calls)}")

        with patch.object(server, "_CACHE_TTL_SECONDS", 10.0), \
             patch.object(server, "_collect_all", side_effect=fake_collect_all), \
             patch.object(server.time, "monotonic", side_effect=[0.0, 0.0, 100.0, 100.0]):
            first = await server.get_snapshot()
            second = await server.get_snapshot()
            assert first is not second
            assert second["cpu"]["tag"] == "v2"
            assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_metrics_endpoint_serves_cached_snapshot(self):
        from fastapi.testclient import TestClient

        server._snapshot = _fake_snapshot("cached")
        server._snapshot_at = 9999999999.0  # fresh for any monotonic time

        client = TestClient(server.app)
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert resp.json()["cpu"]["tag"] == "cached"

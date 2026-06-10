from __future__ import annotations

import os
os.environ.setdefault("MT5_MOCK", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("TRADER_PASSWORD", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("REDIS_PASSWORD", "test")

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_health_returns_healthy() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert data["trading_mode"] in ("demo", "live")


@pytest.mark.asyncio
async def test_health_never_exposes_secrets() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    body = response.text
    assert "password" not in body.lower()
    assert "secret" not in body.lower()
    assert "ghp_" not in body

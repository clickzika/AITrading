from __future__ import annotations

import os

import pytest

os.environ.setdefault("MT5_MOCK", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("TRADER_PASSWORD", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("REDIS_PASSWORD", "test")

from app.services.execution.mt5_client import CircuitState, MT5Client


@pytest.fixture
def client() -> MT5Client:
    return MT5Client(login=12345, password="demo", server="MetaQuotes-Demo", trading_mode="demo")


@pytest.mark.asyncio
async def test_connect_mock_succeeds(client: MT5Client) -> None:
    result = await client.connect()
    assert result is True
    assert client.is_connected()


def test_circuit_starts_closed(client: MT5Client) -> None:
    assert client.circuit_state() == CircuitState.CLOSED


def test_circuit_opens_after_threshold(client: MT5Client) -> None:
    for _ in range(3):
        client._record_failure()
    assert client.circuit_state() == CircuitState.OPEN


def test_circuit_resets_on_success(client: MT5Client) -> None:
    for _ in range(3):
        client._record_failure()
    client._reset_circuit()
    assert client.circuit_state() == CircuitState.CLOSED


def test_get_tick_mock(client: MT5Client) -> None:
    tick = client.get_tick("XAUUSD")
    assert tick is not None
    assert tick.symbol == "XAUUSD"
    assert tick.bid < tick.ask


def test_get_tick_returns_none_when_circuit_open(client: MT5Client) -> None:
    for _ in range(3):
        client._record_failure()
    tick = client.get_tick("XAUUSD")
    assert tick is None


def test_order_send_mock(client: MT5Client) -> None:
    result = client.order_send({"symbol": "XAUUSD", "type": 0, "volume": 0.1})
    assert result["retcode"] == 10009


def test_from_settings_uses_env() -> None:
    client = MT5Client.from_settings()
    assert client.trading_mode in ("demo", "live")

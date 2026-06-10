from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

_MOCK = os.getenv("MT5_MOCK", "false").lower() == "true"

if not _MOCK:
    try:
        import MetaTrader5 as _mt5  # type: ignore[import]
    except ImportError:
        _MOCK = True
        logger.warning("MetaTrader5 not installed — using mock mode")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class TickData:
    symbol: str
    bid: float
    ask: float
    time: float


@dataclass
class MT5Client:
    login: int
    password: str
    server: str
    trading_mode: str = "demo"

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _failure_threshold: int = field(default=3, init=False)
    _half_open_timeout: float = field(default=60.0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _connected: bool = field(default=False, init=False)

    @classmethod
    def from_settings(cls) -> "MT5Client":
        from app.config import settings
        return cls(
            login=settings.mt5_login,
            password=settings.mt5_password,
            server=settings.mt5_server,
            trading_mode=settings.trading_mode,
        )

    async def connect(self) -> bool:
        if _MOCK:
            logger.info("MT5 mock mode — skipping real connection")
            self._connected = True
            return True

        for attempt in range(1, 4):
            try:
                if not _mt5.initialize(
                    login=self.login,
                    password=self.password,
                    server=self.server,
                ):
                    raise RuntimeError(f"MT5 init failed: {_mt5.last_error()}")
                self._connected = True
                self._reset_circuit()
                logger.info("MT5 connected (server=%s, mode=%s)", self.server, self.trading_mode)
                return True
            except Exception as exc:
                logger.warning("MT5 connect attempt %d failed: %s", attempt, exc)
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)
        self._record_failure()
        return False

    def disconnect(self) -> None:
        self._connected = False
        if not _MOCK:
            try:
                _mt5.shutdown()
            except Exception:
                pass

    def is_connected(self) -> bool:
        return self._connected

    def circuit_state(self) -> CircuitState:
        import time
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self._half_open_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info("MT5 circuit → HALF_OPEN")
        return self._state

    def _record_failure(self) -> None:
        import time
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            if self._state != CircuitState.OPEN:
                self._state = CircuitState.OPEN
                logger.warning("MT5 circuit → OPEN after %d failures", self._failure_count)

    def _reset_circuit(self) -> None:
        self._failure_count = 0
        if self._state != CircuitState.CLOSED:
            self._state = CircuitState.CLOSED
            logger.info("MT5 circuit → CLOSED")

    def get_tick(self, symbol: str) -> TickData | None:
        if self.circuit_state() == CircuitState.OPEN:
            return None
        if _MOCK:
            return TickData(symbol=symbol, bid=2341.10, ask=2341.40, time=0.0)
        try:
            tick = _mt5.symbol_info_tick(symbol)
            if tick is None:
                self._record_failure()
                return None
            if self._state == CircuitState.HALF_OPEN:
                self._reset_circuit()
            return TickData(symbol=symbol, bid=tick.bid, ask=tick.ask, time=tick.time)
        except Exception as exc:
            logger.error("get_tick error: %s", exc)
            self._record_failure()
            return None

    def get_ohlcv(self, symbol: str, timeframe: int, count: int = 1000) -> list[dict[str, Any]]:
        if _MOCK:
            return []
        if self.circuit_state() == CircuitState.OPEN:
            return []
        try:
            rates = _mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if rates is None:
                self._record_failure()
                return []
            return [
                {"ts": r["time"], "open": r["open"], "high": r["high"],
                 "low": r["low"], "close": r["close"], "volume": r["tick_volume"]}
                for r in rates
            ]
        except Exception as exc:
            logger.error("get_ohlcv error: %s", exc)
            self._record_failure()
            return []

    def order_send(self, request: dict[str, Any]) -> dict[str, Any]:
        """Send order to MT5. Returns result dict with retcode."""
        if self.trading_mode == "live":
            logger.warning("LIVE TRADING — sending real order: %s", request)
        if _MOCK:
            return {"retcode": 10009, "order": 99999999, "comment": "mock order"}
        if self.circuit_state() == CircuitState.OPEN:
            return {"retcode": -1, "comment": "circuit breaker open"}
        try:
            result = _mt5.order_send(request)
            if result is None:
                self._record_failure()
                return {"retcode": -1, "comment": str(_mt5.last_error())}
            if result.retcode == 10009:
                if self._state == CircuitState.HALF_OPEN:
                    self._reset_circuit()
            else:
                self._record_failure()
            return {"retcode": result.retcode, "order": result.order, "comment": result.comment}
        except Exception as exc:
            logger.error("order_send error: %s", exc)
            self._record_failure()
            return {"retcode": -1, "comment": str(exc)}

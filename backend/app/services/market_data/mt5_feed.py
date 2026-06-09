from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

TICK_THROTTLE_MS = 200  # ms per symbol between publishes
_TIMEFRAME_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900,
    "H1": 3600, "H4": 14400, "D1": 86400,
}


class MT5Feed:
    """Subscribes to MT5 ticks and publishes to Redis pub/sub."""

    def __init__(
        self,
        mt5_client: object,
        redis_client: "aioredis.Redis",
        symbols: list[str],
    ) -> None:
        self._mt5 = mt5_client
        self._redis = redis_client
        self._symbols = symbols
        self._last_publish: dict[str, float] = {}
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("MT5Feed starting for symbols: %s", self._symbols)
        await asyncio.gather(
            self._tick_loop(),
            self._candle_close_loop(),
        )

    def stop(self) -> None:
        self._running = False

    async def _tick_loop(self) -> None:
        while self._running:
            for symbol in self._symbols:
                tick = self._mt5.get_tick(symbol)
                if tick is None:
                    continue
                now = time.time() * 1000
                last = self._last_publish.get(symbol, 0)
                if now - last < TICK_THROTTLE_MS:
                    continue
                self._last_publish[symbol] = now
                payload = json.dumps({
                    "symbol": tick.symbol,
                    "bid": tick.bid,
                    "ask": tick.ask,
                    "ts": tick.time or now / 1000,
                })
                await self._redis.publish(f"tick:{symbol}", payload)
                await self._redis.set(f"price:{symbol}", payload, ex=10)
            await asyncio.sleep(0.05)

    async def _candle_close_loop(self) -> None:
        """Detect candle closes by checking if current bar changed."""
        last_bar: dict[str, int] = {}
        while self._running:
            for symbol in self._symbols:
                for tf_name, tf_sec in _TIMEFRAME_SECONDS.items():
                    current_bar = int(time.time() // tf_sec)
                    key = f"{symbol}:{tf_name}"
                    if key not in last_bar:
                        last_bar[key] = current_bar
                        continue
                    if current_bar != last_bar[key]:
                        last_bar[key] = current_bar
                        await self._on_candle_close(symbol, tf_name)
            await asyncio.sleep(1)

    async def _on_candle_close(self, symbol: str, timeframe: str) -> None:
        payload = json.dumps({"symbol": symbol, "timeframe": timeframe, "ts": time.time()})
        await self._redis.publish(f"candle:{symbol}:{timeframe}", payload)
        logger.debug("Candle close: %s %s", symbol, timeframe)

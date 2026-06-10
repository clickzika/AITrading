from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_TIMEFRAME_MT5 = {
    "M1": 1, "M5": 5, "M15": 15,
    "H1": 16385, "H4": 16388, "D1": 16408,
}


class OHLCVStore:
    """Reads candles from MT5 and writes to TimescaleDB."""

    def __init__(
        self,
        mt5_client: Any = None,
        db_session_factory: Any = None,
    ) -> None:
        self._mt5 = mt5_client
        self._session_factory = db_session_factory

    async def backfill(self, symbol: str, timeframe: str, count: int = 1000) -> int:
        """Fetch historical candles from MT5 and persist to DB."""
        tf_code = _TIMEFRAME_MT5.get(timeframe)
        if tf_code is None:
            raise ValueError(f"Unknown timeframe: {timeframe}")

        candles = self._mt5.get_ohlcv(symbol, tf_code, count)
        if not candles:
            logger.warning("No candles returned for %s %s", symbol, timeframe)
            return 0

        inserted = await self._upsert_candles(symbol, timeframe, candles)
        logger.info("Backfilled %d candles for %s %s", inserted, symbol, timeframe)
        return inserted

    async def _upsert_candles(
        self, symbol: str, timeframe: str, candles: list[dict[str, Any]]
    ) -> int:
        # Imported here to avoid circular imports at module load
        from sqlalchemy import text

        async with self._session_factory() as session:
            count = 0
            for c in candles:
                ts = datetime.fromtimestamp(c["ts"], tz=timezone.utc)
                await session.execute(
                    text("""
                        INSERT INTO ohlcv_candles (ts, symbol, timeframe, open, high, low, close, volume)
                        VALUES (:ts, :symbol, :timeframe, :open, :high, :low, :close, :volume)
                        ON CONFLICT (ts, symbol, timeframe) DO UPDATE
                        SET open=EXCLUDED.open, high=EXCLUDED.high,
                            low=EXCLUDED.low, close=EXCLUDED.close,
                            volume=EXCLUDED.volume
                    """),
                    {"ts": ts, "symbol": symbol, "timeframe": timeframe,
                     "open": c["open"], "high": c["high"], "low": c["low"],
                     "close": c["close"], "volume": c["volume"]},
                )
                count += 1
            await session.commit()
        return count

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> pd.DataFrame | None:
        """
        Fetch candles as a pandas DataFrame (columns: open, high, low, close, volume).
        Returns None if no data source is configured.
        Falls back to MT5 if DB session factory is not set.
        """
        if self._session_factory is not None:
            return await self._get_candles_from_db(symbol, timeframe, limit, from_ts, to_ts)

        if self._mt5 is not None:
            return self._get_candles_from_mt5(symbol, timeframe, limit)

        return None

    async def _get_candles_from_db(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        from_ts: datetime | None,
        to_ts: datetime | None,
    ) -> pd.DataFrame | None:
        from sqlalchemy import text

        async with self._session_factory() as session:
            where = "WHERE symbol = :symbol AND timeframe = :timeframe"
            params: dict[str, Any] = {"symbol": symbol, "timeframe": timeframe, "limit": limit}
            if from_ts:
                where += " AND ts >= :from_ts"
                params["from_ts"] = from_ts
            if to_ts:
                where += " AND ts <= :to_ts"
                params["to_ts"] = to_ts
            rows = await session.execute(
                text(
                    f"SELECT ts, open, high, low, close, volume "
                    f"FROM ohlcv_candles {where} ORDER BY ts ASC LIMIT :limit"
                ),
                params,
            )
            records = rows.fetchall()
            if not records:
                return None
            return pd.DataFrame(
                [{"open": float(r.open), "high": float(r.high), "low": float(r.low),
                  "close": float(r.close), "volume": int(r.volume)}
                 for r in records]
            )

    def _get_candles_from_mt5(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame | None:
        tf_code = _TIMEFRAME_MT5.get(timeframe)
        if tf_code is None:
            return None
        candles = self._mt5.get_ohlcv(symbol, tf_code, limit)
        if not candles:
            return None
        return pd.DataFrame([
            {"open": float(c["open"]), "high": float(c["high"]),
             "low": float(c["low"]), "close": float(c["close"]),
             "volume": int(c.get("volume", 0))}
            for c in candles
        ])

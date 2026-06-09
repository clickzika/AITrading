from __future__ import annotations

import os
os.environ.setdefault("MT5_MOCK", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("TRADER_PASSWORD", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("REDIS_PASSWORD", "test")

import pandas as pd
import pytest

from app.services.smc.order_blocks import detect_order_blocks
from app.services.smc.fvg import detect_fvg
from app.services.smc.bos_choch import detect_bos_choch
from app.services.smc.liquidity import detect_sweeps


def _make_impulse_up() -> pd.DataFrame:
    """Two bearish candles immediately followed by large bullish impulse — triggers Bullish OB."""
    data = {
        "open":  [2300, 2295, 2290, 2360, 2355],
        "high":  [2306, 2300, 2295, 2380, 2370],
        "low":   [2292, 2287, 2282, 2352, 2348],
        "close": [2296, 2291, 2285, 2378, 2365],
        "volume": [1000] * 5,
    }
    return pd.DataFrame(data)


def test_order_block_detects_bullish_ob() -> None:
    df = _make_impulse_up()
    obs = detect_order_blocks(df, impulse_threshold=1.0)
    bullish_obs = [o for o in obs if o["type"] == "bullish"]
    assert len(bullish_obs) >= 1
    assert all("top" in o and "bottom" in o for o in bullish_obs)
    assert all("mitigated" in o for o in bullish_obs)


def test_fvg_detects_bullish_gap() -> None:
    # Bearish impulse: bar1 low (2310) > bar3 high (2298) → bullish FVG in the void
    df = pd.DataFrame({
        "open":  [2360, 2350, 2290, 2295],
        "high":  [2365, 2355, 2298, 2300],
        "low":   [2350, 2310, 2282, 2288],
        "close": [2355, 2315, 2290, 2295],
        "volume": [1000] * 4,
    })
    fvgs = detect_fvg(df)
    bullish = [f for f in fvgs if f["type"] == "bullish"]
    assert len(bullish) >= 1
    assert bullish[0]["top"] > bullish[0]["bottom"]


def test_bos_choch_returns_events() -> None:
    # Create trending data with clear swings
    data = {"open": [], "high": [], "low": [], "close": [], "volume": []}
    price = 2300.0
    for i in range(50):
        data["open"].append(price)
        data["high"].append(price + 5 + (i % 3) * 2)
        data["low"].append(price - 2)
        data["close"].append(price + 3)
        price += 1.5
        data["volume"].append(1000)
    df = pd.DataFrame(data)
    events = detect_bos_choch(df)
    assert isinstance(events, list)


def test_liquidity_sweep_ssl() -> None:
    # Spike below swing low, close above → SSL sweep
    lows = [2300.0] * 20
    highs = [2310.0] * 20
    closes = [2305.0] * 20
    opens = [2303.0] * 20
    # Add one sweep candle
    opens.append(2305.0)
    highs.append(2306.0)
    lows.append(2290.0)  # breaks below 2300 swing low
    closes.append(2304.0)  # closes above
    df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes, "volume": [1000] * 21})
    sweeps = detect_sweeps(df, lookback=20)
    ssl = [s for s in sweeps if s["type"] == "SSL"]
    assert len(ssl) >= 1

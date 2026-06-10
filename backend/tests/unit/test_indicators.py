from __future__ import annotations

import os
os.environ.setdefault("MT5_MOCK", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("TRADER_PASSWORD", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("REDIS_PASSWORD", "test")

import math
import pytest
import pandas as pd
import numpy as np

from app.services.analysis.indicators import (
    compute_ema, compute_macd, get_ema_trend, get_macd_signal,
)
from app.services.analysis.fibonacci import (
    compute_retracement, compute_extension, compute_time_zones,
)
from app.services.analysis.volume_profile import compute_vpvr


def _make_trending_df(n: int = 300) -> pd.DataFrame:
    prices = [2000.0 + i * 0.5 for i in range(n)]
    return pd.DataFrame({
        "open": prices, "high": [p + 2 for p in prices],
        "low": [p - 2 for p in prices], "close": prices,
        "volume": [1000] * n,
    })


def test_ema_requires_min_candles() -> None:
    df = _make_trending_df(50)
    with pytest.raises(ValueError, match="200"):
        compute_ema(df, periods=[200])


def test_ema_returns_correct_length() -> None:
    df = _make_trending_df(300)
    result = compute_ema(df, periods=[20, 50])
    assert len(result["ema20"]) == 300
    assert len(result["ema50"]) == 300


def test_ema_trend_bullish() -> None:
    ema_values = {"ema20": [2350.0], "ema50": [2330.0], "ema200": [2300.0]}
    assert get_ema_trend(ema_values) == "bullish"


def test_ema_trend_bearish() -> None:
    ema_values = {"ema20": [2300.0], "ema50": [2320.0], "ema200": [2350.0]}
    assert get_ema_trend(ema_values) == "bearish"


def test_macd_returns_three_series() -> None:
    df = _make_trending_df(300)
    result = compute_macd(df)
    assert "macd_line" in result
    assert "signal_line" in result
    assert "histogram" in result


def test_macd_signal_bullish_cross() -> None:
    macd = {"macd_line": [0.0, -0.1, 0.1], "signal_line": [0.0, 0.05, 0.05]}
    assert get_macd_signal(macd) == "bullish_cross"


class TestFibonacci:
    def test_retracement_bullish(self) -> None:
        result = compute_retracement(2370.0, 2300.0, "bullish")
        assert result["0.0"] == pytest.approx(2370.0, rel=1e-3)
        assert result["100.0"] == pytest.approx(2300.0, rel=1e-3)
        assert result["61.8"] == pytest.approx(2370.0 - 70.0 * 0.618, rel=1e-3)

    def test_retracement_level_precision_xauusd(self) -> None:
        result = compute_retracement(2370.0, 2300.0, "bullish")
        assert result["38.2"] == pytest.approx(2343.26, abs=0.1)
        assert result["50.0"] == pytest.approx(2335.0, abs=0.1)

    def test_invalid_swing(self) -> None:
        with pytest.raises(ValueError):
            compute_retracement(2300.0, 2370.0)

    def test_time_zones(self) -> None:
        zones = compute_time_zones(10)
        assert zones[0] == 11
        assert zones[4] == 18  # 10 + 8


class TestVolumeProfile:
    def test_poc_is_highest_volume(self) -> None:
        df = _make_trending_df(100)
        vp = compute_vpvr(df, rows=10)
        assert vp.vah >= vp.poc >= vp.val
        assert vp.value_area_pct == 70.0

    def test_zero_range_raises(self) -> None:
        df = pd.DataFrame({
            "open": [2300.0] * 10, "high": [2300.0] * 10,
            "low": [2300.0] * 10, "close": [2300.0] * 10,
            "volume": [1000] * 10,
        })
        with pytest.raises(ValueError):
            compute_vpvr(df)

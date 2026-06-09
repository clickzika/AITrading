from __future__ import annotations

import pandas as pd
import pandas_ta as ta


def compute_ema(df: pd.DataFrame, periods: list[int] | None = None) -> dict[str, list[float]]:
    """Compute EMA for given periods. df must have 'close' column."""
    if periods is None:
        periods = [20, 50, 200]
    if len(df) < max(periods):
        raise ValueError(f"Need at least {max(periods)} candles for EMA-{max(periods)}")
    result: dict[str, list[float]] = {}
    for p in periods:
        series = ta.ema(df["close"], length=p)
        result[f"ema{p}"] = series.round(5).tolist()
    return result


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, list[float]]:
    """Compute MACD. Returns macd_line, signal_line, histogram."""
    macd_df = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
    return {
        "macd_line": macd_df[f"MACD_{fast}_{slow}_{signal}"].round(6).tolist(),
        "signal_line": macd_df[f"MACDs_{fast}_{slow}_{signal}"].round(6).tolist(),
        "histogram": macd_df[f"MACDh_{fast}_{slow}_{signal}"].round(6).tolist(),
    }


def get_ema_trend(ema_values: dict[str, list[float]]) -> str:
    """Classify EMA alignment from most recent values."""
    e20 = _last(ema_values.get("ema20", []))
    e50 = _last(ema_values.get("ema50", []))
    e200 = _last(ema_values.get("ema200", []))
    if e20 is None or e50 is None or e200 is None:
        return "unknown"
    if e20 > e50 > e200:
        return "bullish"
    if e20 < e50 < e200:
        return "bearish"
    return "mixed"


def get_macd_signal(macd_values: dict[str, list[float]]) -> str:
    """Classify MACD signal from last two values."""
    line = macd_values.get("macd_line", [])
    sig = macd_values.get("signal_line", [])
    if len(line) < 2 or len(sig) < 2:
        return "neutral"
    prev_cross = line[-2] - sig[-2]
    curr_cross = line[-1] - sig[-1]
    if prev_cross <= 0 < curr_cross:
        return "bullish_cross"
    if prev_cross >= 0 > curr_cross:
        return "bearish_cross"
    return "bullish" if curr_cross > 0 else "bearish"


def get_ema20_position(ema_values: dict[str, list[float]]) -> str:
    e20 = _last(ema_values.get("ema20", []))
    e50 = _last(ema_values.get("ema50", []))
    if e20 is None or e50 is None:
        return "unknown"
    return "above_ema50" if e20 > e50 else "below_ema50"


def _last(lst: list[float]) -> float | None:
    for v in reversed(lst):
        if v == v:  # not NaN
            return v
    return None

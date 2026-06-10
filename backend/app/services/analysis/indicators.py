from __future__ import annotations

import pandas as pd

try:
    import pandas_ta as ta
    _HAS_PANDAS_TA = True
except (ImportError, ModuleNotFoundError):
    ta = None  # type: ignore[assignment]
    _HAS_PANDAS_TA = False


def _ema_series(close: pd.Series, period: int) -> pd.Series:
    if _HAS_PANDAS_TA and ta is not None:
        return ta.ema(close, length=period)
    return close.ewm(span=period, adjust=False).mean()


def _macd_series(
    close: pd.Series, fast: int, slow: int, signal: int
) -> tuple[pd.Series, pd.Series, pd.Series]:
    if _HAS_PANDAS_TA and ta is not None:
        macd_df = ta.macd(close, fast=fast, slow=slow, signal=signal)
        col_m = f"MACD_{fast}_{slow}_{signal}"
        col_s = f"MACDs_{fast}_{slow}_{signal}"
        col_h = f"MACDh_{fast}_{slow}_{signal}"
        return macd_df[col_m], macd_df[col_s], macd_df[col_h]
    # Pure-pandas fallback
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_ema(df: pd.DataFrame, periods: list[int] | None = None) -> dict[str, list[float]]:
    """Compute EMA for given periods. df must have 'close' column."""
    if periods is None:
        periods = [20, 50, 200]
    if len(df) < max(periods):
        raise ValueError(f"Need at least {max(periods)} candles for EMA-{max(periods)}")
    result: dict[str, list[float]] = {}
    for p in periods:
        series = _ema_series(df["close"], p)
        result[f"ema{p}"] = series.round(5).tolist()
    return result


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, list[float]]:
    """Compute MACD. Returns macd_line, signal_line, histogram."""
    macd_line, signal_line, histogram = _macd_series(df["close"], fast, slow, signal)
    return {
        "macd_line": macd_line.round(6).tolist(),
        "signal_line": signal_line.round(6).tolist(),
        "histogram": histogram.round(6).tolist(),
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

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_PATTERN_DESCRIPTIONS: dict[str, str] = {
    "CDL2CROWS": "Two Crows",
    "CDL3BLACKCROWS": "Three Black Crows",
    "CDL3INSIDE": "Three Inside Up/Down",
    "CDL3LINESTRIKE": "Three Line Strike",
    "CDL3OUTSIDE": "Three Outside Up/Down",
    "CDL3STARSINSOUTH": "Three Stars In The South",
    "CDL3WHITESOLDIERS": "Three Advancing White Soldiers",
    "CDLABANDONEDBABY": "Abandoned Baby",
    "CDLDOJI": "Doji",
    "CDLDRAGONFLYDOJI": "Dragonfly Doji",
    "CDLENGULFING": "Engulfing Pattern",
    "CDLEVENINGDOJISTAR": "Evening Doji Star",
    "CDLEVENINGSTAR": "Evening Star",
    "CDLHAMMER": "Hammer",
    "CDLHANGINGMAN": "Hanging Man",
    "CDLHARAMI": "Harami Pattern",
    "CDLHARAMICROSS": "Harami Cross Pattern",
    "CDLINVERTEDHAMMER": "Inverted Hammer",
    "CDLMARUBOZU": "Marubozu",
    "CDLMORNINGDOJISTAR": "Morning Doji Star",
    "CDLMORNINGSTAR": "Morning Star",
    "CDLPIERCING": "Piercing Pattern",
    "CDLSHOOTINGSTAR": "Shooting Star",
    "CDLSPINNINGTOP": "Spinning Top",
}


def detect_patterns(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Detect candlestick patterns using TA-Lib CDL functions.
    Falls back to basic manual patterns if TA-Lib not available.
    """
    try:
        import talib  # type: ignore[import]
        return _detect_talib(df, talib)
    except ImportError:
        logger.warning("TA-Lib not available — using basic pattern detection")
        return _detect_basic(df)


def _detect_talib(df: pd.DataFrame, talib: Any) -> list[dict[str, Any]]:
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    results: list[dict[str, Any]] = []
    for pattern_name, description in _PATTERN_DESCRIPTIONS.items():
        fn = getattr(talib, pattern_name, None)
        if fn is None:
            continue
        signals = fn(o, h, l, c)
        for i, sig in enumerate(signals):
            if sig != 0:
                ts = df.index[i] if hasattr(df.index[i], "isoformat") else None
                results.append({
                    "bar_index": i - len(df) + 1,
                    "ts": ts.isoformat() if ts else None,
                    "pattern": pattern_name,
                    "signal": int(sig),
                    "description": description,
                })
    return results


def _detect_basic(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Minimal fallback: detect Engulfing and Doji without TA-Lib."""
    results: list[dict[str, Any]] = []
    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]
        body = abs(curr["close"] - curr["open"])
        prev_body = abs(prev["close"] - prev["open"])
        # Bullish engulfing
        if (prev["close"] < prev["open"] and curr["close"] > curr["open"]
                and curr["open"] < prev["close"] and curr["close"] > prev["open"]):
            results.append({"bar_index": i - len(df) + 1, "ts": None,
                            "pattern": "CDLENGULFING", "signal": 100,
                            "description": "Bullish Engulfing"})
        # Bearish engulfing
        elif (prev["close"] > prev["open"] and curr["close"] < curr["open"]
              and curr["open"] > prev["close"] and curr["close"] < prev["open"]):
            results.append({"bar_index": i - len(df) + 1, "ts": None,
                            "pattern": "CDLENGULFING", "signal": -100,
                            "description": "Bearish Engulfing"})
        # Doji: body < 10% of range
        candle_range = curr["high"] - curr["low"]
        if candle_range > 0 and body / candle_range < 0.1:
            results.append({"bar_index": i - len(df) + 1, "ts": None,
                            "pattern": "CDLDOJI", "signal": 0,
                            "description": "Doji"})
    return results

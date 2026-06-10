from __future__ import annotations

from typing import Any

import pandas as pd


def detect_wick_fills(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Detect wick fill scenarios: candle closes past previous candle's wick extreme.
    Bullish: current close > previous high (fills upper wick)
    Bearish: current close < previous low (fills lower wick)
    """
    results: list[dict[str, Any]] = []
    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]
        if curr["close"] > prev["high"]:
            results.append({
                "bar_index": i - len(df) + 1,
                "type": "wick_fill_bullish",
                "price": float(prev["high"]),
                "direction": "bullish",
            })
        elif curr["close"] < prev["low"]:
            results.append({
                "bar_index": i - len(df) + 1,
                "type": "wick_fill_bearish",
                "price": float(prev["low"]),
                "direction": "bearish",
            })
    return results


def detect_sl_sweeps(df: pd.DataFrame, lookback: int = 10) -> list[dict[str, Any]]:
    """
    Detect stop loss sweep: price briefly breaks a swing level then reverses sharply.
    SSL sweep: low breaks below recent swing low then closes above it.
    BSL sweep: high breaks above recent swing high then closes below it.
    """
    results: list[dict[str, Any]] = []
    for i in range(lookback, len(df)):
        window = df.iloc[i - lookback:i]
        curr = df.iloc[i]
        swing_low = window["low"].min()
        swing_high = window["high"].max()

        # SSL: wick below swing low but close above it
        if curr["low"] < swing_low and curr["close"] > swing_low:
            results.append({
                "bar_index": i - len(df) + 1,
                "type": "SSL",
                "price": float(swing_low),
                "direction": "bullish",
            })

        # BSL: wick above swing high but close below it
        if curr["high"] > swing_high and curr["close"] < swing_high:
            results.append({
                "bar_index": i - len(df) + 1,
                "type": "BSL",
                "price": float(swing_high),
                "direction": "bearish",
            })
    return results

from __future__ import annotations

from typing import Any

import pandas as pd


def detect_bos_choch(df: pd.DataFrame, swing_lookback: int = 5) -> list[dict[str, Any]]:
    """
    Detect Break of Structure (BOS) and Change of Character (ChoCH).

    State machine:
    - Identifies swing highs/lows with lookback window
    - BOS: break that continues the current trend (higher high in uptrend / lower low in downtrend)
    - ChoCH: break that reverses the current trend
    """
    results: list[dict[str, Any]] = []
    if len(df) < swing_lookback * 2 + 1:
        return results

    swings = _find_swings(df, swing_lookback)
    if not swings:
        return results

    current_bias = _determine_initial_bias(swings)
    last_significant_high = _last_swing(swings, "high")
    last_significant_low = _last_swing(swings, "low")

    for i in range(swing_lookback, len(df)):
        close = float(df.iloc[i]["close"])

        if last_significant_high and close > last_significant_high["price"]:
            event_type = "BOS" if current_bias == "bullish" else "ChoCH"
            results.append({
                "type": event_type,
                "direction": "bullish",
                "price": last_significant_high["price"],
                "bar_index": i - len(df) + 1,
            })
            current_bias = "bullish"
            last_significant_high = {"price": close, "idx": i}

        elif last_significant_low and close < last_significant_low["price"]:
            event_type = "BOS" if current_bias == "bearish" else "ChoCH"
            results.append({
                "type": event_type,
                "direction": "bearish",
                "price": last_significant_low["price"],
                "bar_index": i - len(df) + 1,
            })
            current_bias = "bearish"
            last_significant_low = {"price": close, "idx": i}

    return results


def _find_swings(df: pd.DataFrame, lookback: int) -> list[dict[str, Any]]:
    swings: list[dict[str, Any]] = []
    for i in range(lookback, len(df) - lookback):
        window_high = df.iloc[i - lookback:i + lookback + 1]["high"]
        window_low = df.iloc[i - lookback:i + lookback + 1]["low"]
        if df.iloc[i]["high"] == window_high.max():
            swings.append({"type": "high", "price": float(df.iloc[i]["high"]), "idx": i})
        elif df.iloc[i]["low"] == window_low.min():
            swings.append({"type": "low", "price": float(df.iloc[i]["low"]), "idx": i})
    return swings


def _determine_initial_bias(swings: list[dict[str, Any]]) -> str:
    highs = [s for s in swings if s["type"] == "high"]
    lows = [s for s in swings if s["type"] == "low"]
    if len(highs) >= 2 and highs[-1]["price"] > highs[-2]["price"]:
        return "bullish"
    if len(lows) >= 2 and lows[-1]["price"] < lows[-2]["price"]:
        return "bearish"
    return "bullish"


def _last_swing(swings: list[dict[str, Any]], swing_type: str) -> dict[str, Any] | None:
    for s in reversed(swings):
        if s["type"] == swing_type:
            return s
    return None

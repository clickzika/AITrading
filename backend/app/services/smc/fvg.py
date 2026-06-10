from __future__ import annotations

from typing import Any

import pandas as pd


def detect_fvg(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Detect Fair Value Gaps (3-candle imbalance patterns).
    Bullish FVG: candle[i-1].low > candle[i+1].high (gap up between candle 0 and candle 2)
    Bearish FVG: candle[i-1].high < candle[i+1].low (gap down)
    Tracks fill status from subsequent price action.
    """
    results: list[dict[str, Any]] = []

    for i in range(1, len(df) - 1):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]  # noqa: F841 — middle candle defines the gap
        nxt = df.iloc[i + 1]

        # Bullish FVG: nxt.high < prev.low (price gapped up leaving a void below)
        if nxt["high"] < prev["low"]:
            fvg = {
                "type": "bullish",
                "top": float(prev["low"]),
                "bottom": float(nxt["high"]),
                "bar_index": i - len(df) + 1,
                "filled": False,
            }
            fvg["filled"] = _is_filled_bullish(df, i, fvg["bottom"])
            results.append(fvg)

        # Bearish FVG: nxt.low > prev.high (price gapped down leaving void above)
        elif nxt["low"] > prev["high"]:
            fvg = {
                "type": "bearish",
                "top": float(nxt["low"]),
                "bottom": float(prev["high"]),
                "bar_index": i - len(df) + 1,
                "filled": False,
            }
            fvg["filled"] = _is_filled_bearish(df, i, fvg["top"])
            results.append(fvg)

    return results


def _is_filled_bullish(df: pd.DataFrame, fvg_idx: int, fvg_bottom: float) -> bool:
    for i in range(fvg_idx + 2, len(df)):
        if df.iloc[i]["low"] <= fvg_bottom:
            return True
    return False


def _is_filled_bearish(df: pd.DataFrame, fvg_idx: int, fvg_top: float) -> bool:
    for i in range(fvg_idx + 2, len(df)):
        if df.iloc[i]["high"] >= fvg_top:
            return True
    return False

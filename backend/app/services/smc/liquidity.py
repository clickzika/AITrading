from __future__ import annotations

from typing import Any

import pandas as pd


def detect_sweeps(df: pd.DataFrame, lookback: int = 20) -> list[dict[str, Any]]:
    """
    Detect Buy-Side Liquidity (BSL) and Sell-Side Liquidity (SSL) sweeps.
    BSL sweep: high exceeds previous swing high then closes below it.
    SSL sweep: low breaks previous swing low then closes above it.
    """
    results: list[dict[str, Any]] = []

    for i in range(lookback, len(df)):
        window = df.iloc[i - lookback:i]
        curr = df.iloc[i]
        swing_high = float(window["high"].max())
        swing_low = float(window["low"].min())

        # BSL sweep: wick above swing high, close below it
        if curr["high"] > swing_high and curr["close"] < swing_high:
            results.append({
                "type": "BSL",
                "price": swing_high,
                "bar_index": i - len(df) + 1,
                "direction": "bearish",
            })

        # SSL sweep: wick below swing low, close above it
        elif curr["low"] < swing_low and curr["close"] > swing_low:
            results.append({
                "type": "SSL",
                "price": swing_low,
                "bar_index": i - len(df) + 1,
                "direction": "bullish",
            })

    return results

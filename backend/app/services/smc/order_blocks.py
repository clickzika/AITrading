from __future__ import annotations

from typing import Any

import pandas as pd


def detect_order_blocks(df: pd.DataFrame, impulse_threshold: float = 1.5) -> list[dict[str, Any]]:
    """
    Detect Order Blocks: last opposing candle before an impulsive move.
    Bullish OB: last bearish candle before a bullish impulse.
    Bearish OB: last bullish candle before a bearish impulse.
    Tracks mitigation (price revisiting the OB).
    """
    results: list[dict[str, Any]] = []
    avg_body = _avg_body(df)

    for i in range(2, len(df) - 1):
        curr = df.iloc[i]
        next_c = df.iloc[i + 1] if i + 1 < len(df) else None
        if next_c is None:
            continue

        curr_body = abs(curr["close"] - curr["open"])
        next_body = abs(next_c["close"] - next_c["open"])

        # Bullish OB: current is bearish, next is impulsive bullish
        if (curr["close"] < curr["open"]
                and next_c["close"] > next_c["open"]
                and next_body > avg_body * impulse_threshold):
            ob = {
                "type": "bullish",
                "top": float(curr["open"]),
                "bottom": float(curr["close"]),
                "bar_index": i - len(df) + 1,
                "mitigated": False,
            }
            ob["mitigated"] = _is_mitigated_bullish(df, i, ob["bottom"])
            results.append(ob)

        # Bearish OB: current is bullish, next is impulsive bearish
        elif (curr["close"] > curr["open"]
              and next_c["close"] < next_c["open"]
              and next_body > avg_body * impulse_threshold):
            ob = {
                "type": "bearish",
                "top": float(curr["close"]),
                "bottom": float(curr["open"]),
                "bar_index": i - len(df) + 1,
                "mitigated": False,
            }
            ob["mitigated"] = _is_mitigated_bearish(df, i, ob["top"])
            results.append(ob)

    return results


def _avg_body(df: pd.DataFrame) -> float:
    bodies = abs(df["close"] - df["open"])
    avg = bodies.mean()
    return float(avg) if avg > 0 else 1.0


def _is_mitigated_bullish(df: pd.DataFrame, ob_idx: int, ob_bottom: float) -> bool:
    """Bullish OB is mitigated when price trades into its bottom 50%."""
    for i in range(ob_idx + 2, len(df)):
        if df.iloc[i]["low"] <= ob_bottom:
            return True
    return False


def _is_mitigated_bearish(df: pd.DataFrame, ob_idx: int, ob_top: float) -> bool:
    """Bearish OB is mitigated when price trades into its top 50%."""
    for i in range(ob_idx + 2, len(df)):
        if df.iloc[i]["high"] >= ob_top:
            return True
    return False

from __future__ import annotations

from typing import Any

import pandas as pd


def detect_demand_supply_zones(df: pd.DataFrame, impulse_threshold: float = 1.5) -> dict[str, list[dict[str, Any]]]:
    """
    Identify Demand and Supply zones from price action.
    Demand zone: base of strong bullish move (accumulation before impulse up).
    Supply zone: base of strong bearish move (distribution before impulse down).
    Strength = number of times price returned without mitigating.
    """
    avg_body = _avg_body(df)
    demand: list[dict[str, Any]] = []
    supply: list[dict[str, Any]] = []

    for i in range(1, len(df) - 1):
        curr = df.iloc[i]
        nxt = df.iloc[i + 1]
        nxt_body = abs(nxt["close"] - nxt["open"])

        if nxt_body > avg_body * impulse_threshold:
            if nxt["close"] > nxt["open"]:
                # Demand zone: base of the move
                zone = {
                    "top": max(float(curr["open"]), float(curr["close"])),
                    "bottom": min(float(curr["open"]), float(curr["close"])),
                    "bar_index": i - len(df) + 1,
                    "strength": 1,
                }
                zone["strength"] = _count_revisits(df, i + 2, zone["bottom"], zone["top"], "demand")
                demand.append(zone)
            else:
                zone = {
                    "top": max(float(curr["open"]), float(curr["close"])),
                    "bottom": min(float(curr["open"]), float(curr["close"])),
                    "bar_index": i - len(df) + 1,
                    "strength": 1,
                }
                zone["strength"] = _count_revisits(df, i + 2, zone["bottom"], zone["top"], "supply")
                supply.append(zone)

    return {"demand_zones": demand, "supply_zones": supply}


def detect_sr_zones(df: pd.DataFrame, tolerance_pct: float = 0.001) -> list[dict[str, Any]]:
    """
    Detect horizontal Support/Resistance zones by clustering price levels with 2+ touches.
    """
    levels: list[float] = []
    for i in range(1, len(df) - 1):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        nxt = df.iloc[i + 1]
        if row["high"] > prev["high"] and row["high"] > nxt["high"]:
            levels.append(float(row["high"]))
        if row["low"] < prev["low"] and row["low"] < nxt["low"]:
            levels.append(float(row["low"]))

    zones = _cluster_levels(levels, tolerance_pct)
    return sorted(zones, key=lambda z: z["strength"], reverse=True)


def _cluster_levels(levels: list[float], tolerance_pct: float) -> list[dict[str, Any]]:
    if not levels:
        return []
    levels_sorted = sorted(levels)
    clusters: list[dict[str, Any]] = []
    current_cluster = [levels_sorted[0]]

    for lvl in levels_sorted[1:]:
        if abs(lvl - current_cluster[-1]) / current_cluster[-1] <= tolerance_pct:
            current_cluster.append(lvl)
        else:
            if len(current_cluster) >= 2:
                mid = sum(current_cluster) / len(current_cluster)
                clusters.append({
                    "price": round(mid, 5),
                    "strength": len(current_cluster),
                    "type": "major" if len(current_cluster) >= 3 else "minor",
                })
            current_cluster = [lvl]

    if len(current_cluster) >= 2:
        mid = sum(current_cluster) / len(current_cluster)
        clusters.append({
            "price": round(mid, 5),
            "strength": len(current_cluster),
            "type": "major" if len(current_cluster) >= 3 else "minor",
        })
    return clusters


def _count_revisits(
    df: pd.DataFrame, start: int, bottom: float, top: float, zone_type: str
) -> int:
    count = 1
    for i in range(start, len(df)):
        row = df.iloc[i]
        if zone_type == "demand" and row["low"] >= bottom and row["low"] <= top:
            count += 1
        elif zone_type == "supply" and row["high"] >= bottom and row["high"] <= top:
            count += 1
    return count


def _avg_body(df: pd.DataFrame) -> float:
    bodies = abs(df["close"] - df["open"])
    avg = bodies.mean()
    return float(avg) if avg > 0 else 1.0

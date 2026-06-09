from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class VolumeProfileRow:
    price_low: float
    price_high: float
    volume: float


@dataclass
class VolumeProfile:
    poc: float
    vah: float
    val: float
    value_area_pct: float
    rows: list[VolumeProfileRow]


def compute_vpvr(df: pd.DataFrame, rows: int = 24) -> VolumeProfile:
    """
    Compute Volume Profile Visible Range (VPVR).
    Returns POC, VAH, VAL using the 70% volume rule.
    df must have columns: high, low, close, volume.
    """
    price_min = df["low"].min()
    price_max = df["high"].max()
    if price_max == price_min:
        raise ValueError("Price range is zero — cannot compute volume profile")

    bucket_size = (price_max - price_min) / rows
    buckets: list[VolumeProfileRow] = []
    for i in range(rows):
        p_low = price_min + i * bucket_size
        p_high = p_low + bucket_size
        buckets.append(VolumeProfileRow(price_low=round(p_low, 5), price_high=round(p_high, 5), volume=0.0))

    # Distribute volume to buckets by typical price
    for _, row in df.iterrows():
        typical = (row["high"] + row["low"] + row["close"]) / 3
        idx = min(int((typical - price_min) / bucket_size), rows - 1)
        buckets[idx].volume += float(row["volume"])

    # POC = highest volume bucket midpoint
    poc_bucket = max(buckets, key=lambda b: b.volume)
    poc = round((poc_bucket.price_low + poc_bucket.price_high) / 2, 5)

    # Value Area = 70% of total volume centered on POC
    total_vol = sum(b.volume for b in buckets)
    target = total_vol * 0.70

    poc_idx = buckets.index(poc_bucket)
    lo_idx = hi_idx = poc_idx
    va_vol = poc_bucket.volume

    while va_vol < target:
        extend_low = buckets[lo_idx - 1].volume if lo_idx > 0 else 0
        extend_high = buckets[hi_idx + 1].volume if hi_idx < rows - 1 else 0
        if extend_low >= extend_high and lo_idx > 0:
            lo_idx -= 1
            va_vol += extend_low
        elif hi_idx < rows - 1:
            hi_idx += 1
            va_vol += extend_high
        else:
            break

    vah = round(buckets[hi_idx].price_high, 5)
    val = round(buckets[lo_idx].price_low, 5)

    return VolumeProfile(poc=poc, vah=vah, val=val, value_area_pct=70.0, rows=buckets)

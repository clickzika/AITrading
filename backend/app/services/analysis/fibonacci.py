from __future__ import annotations

_RETRACEMENT_LEVELS = [0.0, 23.6, 38.2, 50.0, 61.8, 78.6, 100.0]
_EXTENSION_LEVELS = [127.2, 161.8, 261.8]
_FIBONACCI_SEQUENCE = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]


def compute_retracement(
    swing_high: float,
    swing_low: float,
    direction: str = "bullish",
) -> dict[str, float]:
    """
    Compute Fibonacci retracement levels.
    direction='bullish': price retracing from swing_high down toward swing_low.
    direction='bearish': price retracing from swing_low up toward swing_high.
    Recomputes on candle close only (not per tick).
    """
    diff = swing_high - swing_low
    if diff <= 0:
        raise ValueError("swing_high must be greater than swing_low")

    result: dict[str, float] = {}
    for level in _RETRACEMENT_LEVELS:
        pct = level / 100.0
        if direction == "bullish":
            result[str(level)] = round(swing_high - diff * pct, 5)
        else:
            result[str(level)] = round(swing_low + diff * pct, 5)
    return result


def compute_extension(
    swing_high: float,
    swing_low: float,
    direction: str = "bullish",
) -> dict[str, float]:
    diff = swing_high - swing_low
    result: dict[str, float] = {}
    for level in _EXTENSION_LEVELS:
        pct = level / 100.0
        if direction == "bullish":
            result[str(level)] = round(swing_low + diff * pct, 5)
        else:
            result[str(level)] = round(swing_high - diff * pct, 5)
    return result


def compute_time_zones(swing_bar_index: int) -> list[int]:
    """Return bar indices at Fibonacci multiples from the reference swing bar."""
    return [swing_bar_index + fib for fib in _FIBONACCI_SEQUENCE]

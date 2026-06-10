from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class HedgePosition:
    primary_direction: Literal["buy", "sell"]
    primary_lot: float
    hedge_lot: float
    hedge_ratio: float  # fraction of primary lot to hedge (e.g. 1.0 = full hedge)
    hedge_order_id: str | None = None
    active: bool = False


def open_hedge(
    primary_direction: Literal["buy", "sell"],
    primary_lot: float,
    hedge_ratio: float = 1.0,
    max_lot: float = 10.0,
) -> HedgePosition:
    """
    Create a hedge instruction opposite to the primary direction.
    hedge_ratio: 1.0 = full hedge, 0.5 = half hedge.
    """
    if not 0 < hedge_ratio <= 2.0:
        raise ValueError(f"hedge_ratio must be between 0 and 2.0, got {hedge_ratio}")

    hedge_lot = round(min(primary_lot * hedge_ratio, max_lot), 2)
    hedge_lot = max(hedge_lot, 0.01)

    return HedgePosition(
        primary_direction=primary_direction,
        primary_lot=primary_lot,
        hedge_lot=hedge_lot,
        hedge_ratio=hedge_ratio,
        active=True,
    )


def hedge_direction(primary: Literal["buy", "sell"]) -> Literal["buy", "sell"]:
    return "sell" if primary == "buy" else "buy"


def net_exposure(primary_lot: float, hedge_lot: float) -> float:
    """Net directional exposure after hedging."""
    return round(primary_lot - hedge_lot, 2)

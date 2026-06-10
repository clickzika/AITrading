from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class GridLevel:
    price: float
    lot: float
    direction: Literal["buy", "sell"]
    order_id: str | None = None
    filled: bool = False


@dataclass
class GridState:
    base_price: float
    levels: list[GridLevel]
    spacing: float
    base_lot: float
    max_lot: float
    direction: Literal["buy", "sell", "both"]
    open_count: int = 0


def build_grid(
    base_price: float,
    levels: int,
    spacing: float,
    base_lot: float,
    max_lot: float,
    direction: Literal["buy", "sell", "both"] = "both",
) -> GridState:
    """
    Build grid levels around base_price.
    spacing: price distance between levels (in quote currency units).
    """
    grid_levels: list[GridLevel] = []

    for i in range(1, levels + 1):
        if direction in ("buy", "both"):
            grid_levels.append(GridLevel(
                price=round(base_price - i * spacing, 5),
                lot=min(base_lot, max_lot),
                direction="buy",
            ))
        if direction in ("sell", "both"):
            grid_levels.append(GridLevel(
                price=round(base_price + i * spacing, 5),
                lot=min(base_lot, max_lot),
                direction="sell",
            ))

    grid_levels.sort(key=lambda g: g.price)
    return GridState(
        base_price=base_price,
        levels=grid_levels,
        spacing=spacing,
        base_lot=base_lot,
        max_lot=max_lot,
        direction=direction,
    )


def get_triggered_levels(state: GridState, current_price: float) -> list[GridLevel]:
    """Return unfilled levels where price has crossed the trigger price."""
    triggered: list[GridLevel] = []
    for level in state.levels:
        if level.filled:
            continue
        if level.direction == "buy" and current_price <= level.price:
            triggered.append(level)
        elif level.direction == "sell" and current_price >= level.price:
            triggered.append(level)
    return triggered


def rebuild_grid(state: GridState, new_base_price: float) -> GridState:
    """Rebuild grid around a new base price (e.g. after all levels filled)."""
    return build_grid(
        base_price=new_base_price,
        levels=len(state.levels) // (2 if state.direction == "both" else 1),
        spacing=state.spacing,
        base_lot=state.base_lot,
        max_lot=state.max_lot,
        direction=state.direction,
    )

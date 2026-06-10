from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class Position:
    ticket: int
    symbol: str
    direction: str  # "buy" or "sell"
    lot_size: float
    open_price: float
    current_price: float
    stop_loss: float | None
    take_profit: float | None
    profit: float
    magic: int = 0
    comment: str = ""


class PositionManager:
    """
    Manages open positions: monitoring, trailing stops, partial close.
    """

    def __init__(self, mt5_client: Any) -> None:
        self._mt5 = mt5_client

    def get_open_positions(self, symbol: str | None = None) -> list[Position]:
        """Fetch open positions from MT5. Optionally filtered by symbol."""
        raw_positions = self._mt5.positions_get(symbol=symbol)
        if not raw_positions:
            return []
        return [self._parse_position(p) for p in raw_positions]

    def count_open_positions(self, symbol: str | None = None) -> int:
        return len(self.get_open_positions(symbol))

    def close_position(self, ticket: int, lot_size: float | None = None) -> bool:
        """
        Close a position fully (lot_size=None) or partially.
        Returns True on success.
        """
        positions = self._mt5.positions_get(ticket=ticket)
        if not positions:
            log.warning("Close failed: ticket %d not found", ticket)
            return False

        pos = positions[0]
        close_lot = lot_size or pos.get("volume", 0.01)
        close_type = 1 if pos.get("type") == 0 else 0  # opposite direction

        request = {
            "action": 1,  # TRADE_ACTION_DEAL
            "symbol": pos.get("symbol"),
            "volume": close_lot,
            "type": close_type,
            "position": ticket,
            "deviation": 10,
            "magic": pos.get("magic", 0),
            "comment": "close",
            "type_time": 0,
            "type_filling": 1,
        }
        result = self._mt5.order_send(request)
        success = result.get("retcode") == 10009
        if not success:
            log.warning("Close position %d failed: retcode=%s", ticket, result.get("retcode"))
        return success

    def close_all_positions(self, symbol: str | None = None) -> int:
        """Close all open positions. Returns count closed successfully."""
        positions = self.get_open_positions(symbol)
        closed = sum(1 for p in positions if self.close_position(p.ticket))
        return closed

    def update_trailing_stop(
        self,
        ticket: int,
        current_price: float,
        trail_pips: float,
        pip_size: float = 0.0001,
        direction: str = "buy",
    ) -> bool:
        """
        Move stop loss to lock in profit as price moves in favour.
        Only moves the SL in the profitable direction — never against the trade.
        """
        positions = self._mt5.positions_get(ticket=ticket)
        if not positions:
            return False

        pos = positions[0]
        current_sl = pos.get("sl") or 0.0
        trail_distance = trail_pips * pip_size

        if direction == "buy":
            new_sl = round(current_price - trail_distance, 5)
            if new_sl <= current_sl:
                return False  # no improvement
        else:
            new_sl = round(current_price + trail_distance, 5)
            if current_sl > 0 and new_sl >= current_sl:
                return False

        request = {
            "action": 6,  # TRADE_ACTION_SLTP
            "position": ticket,
            "sl": new_sl,
            "tp": pos.get("tp") or 0.0,
        }
        result = self._mt5.order_send(request)
        return result.get("retcode") == 10009

    def get_total_profit(self, symbol: str | None = None) -> float:
        """Sum of floating P&L across all open positions."""
        return sum(p.profit for p in self.get_open_positions(symbol))

    @staticmethod
    def _parse_position(raw: Any) -> Position:
        if hasattr(raw, "_asdict"):
            raw = raw._asdict()
        direction = "buy" if raw.get("type") == 0 else "sell"
        return Position(
            ticket=int(raw.get("ticket", 0)),
            symbol=str(raw.get("symbol", "")),
            direction=direction,
            lot_size=float(raw.get("volume", 0)),
            open_price=float(raw.get("price_open", 0)),
            current_price=float(raw.get("price_current", 0)),
            stop_loss=raw.get("sl") or None,
            take_profit=raw.get("tp") or None,
            profit=float(raw.get("profit", 0)),
            magic=int(raw.get("magic", 0)),
            comment=str(raw.get("comment", "")),
        )

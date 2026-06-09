from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.strategy.models import RiskConfig, RiskMethodEnum


@dataclass
class RiskCalculation:
    lot_size: float
    stop_loss_price: float | None
    take_profit_price: float | None
    risk_usd: float | None
    method: str


@dataclass
class DailyLossTracker:
    """Thread-safe daily loss accumulator. Reset each trading day."""
    max_loss_usd: float
    _realized_loss: float = field(default=0.0, init=False)

    def record_loss(self, usd: float) -> None:
        """usd is a positive value representing a loss amount."""
        self._realized_loss += abs(usd)

    def record_profit(self, usd: float) -> None:
        self._realized_loss -= abs(usd)
        self._realized_loss = max(0.0, self._realized_loss)

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.max_loss_usd - self._realized_loss)

    @property
    def is_breached(self) -> bool:
        return self._realized_loss >= self.max_loss_usd

    def reset(self) -> None:
        self._realized_loss = 0.0


def calculate_lot_size(
    risk: RiskConfig,
    account_balance: float,
    stop_loss_pips: float | None = None,
    pip_value: float = 10.0,
    win_rate: float | None = None,
    avg_win_loss_ratio: float | None = None,
) -> float:
    """
    Calculate lot size based on the risk method.
    pip_value: USD value per pip per standard lot (default 10 for XAUUSD/majors).
    Returns a lot size clamped to [0.01, max_lot_size].
    """
    stop_pips = stop_loss_pips or risk.stop_loss_pips or 30.0

    if risk.method == RiskMethodEnum.FIXED_LOT:
        raw = risk.lot_size or 0.01

    elif risk.method == RiskMethodEnum.FIXED_FRACTIONAL:
        risk_usd = account_balance * (risk.risk_pct or 1.0) / 100.0
        raw = risk_usd / (stop_pips * pip_value)

    elif risk.method == RiskMethodEnum.KELLY:
        if win_rate is None or avg_win_loss_ratio is None:
            # Fall back to 0.5% risk when no stats available
            raw = (account_balance * 0.005) / (stop_pips * pip_value)
        else:
            kelly_pct = win_rate - (1 - win_rate) / avg_win_loss_ratio
            half_kelly = max(0.0, kelly_pct / 2.0)
            max_pct = (risk.risk_pct or 2.0) / 100.0
            pct = min(half_kelly, max_pct)
            risk_usd = account_balance * pct
            raw = risk_usd / (stop_pips * pip_value)

    elif risk.method == RiskMethodEnum.MARTINGALE:
        # Caller must provide current_multiplier in kwargs — base size passed as lot_size
        raw = risk.lot_size or 0.01

    else:
        raw = 0.01

    return _clamp_lot(raw, risk.max_lot_size)


def calculate_martingale_lot(
    risk: RiskConfig,
    base_lot: float,
    consecutive_losses: int,
) -> float:
    """
    Calculate martingale lot for current position in loss streak.
    Enforces max_multiplier and max_lot_size — both are required (no defaults).
    """
    multiplier = risk.multiplier or 2.0
    max_mult = risk.max_multiplier  # required field
    if max_mult is None:
        raise ValueError("max_multiplier is required for martingale — safety rule")

    effective_mult = min(multiplier ** consecutive_losses, max_mult)
    raw = base_lot * effective_mult
    return _clamp_lot(raw, risk.max_lot_size)


def compute_sl_tp(
    entry_price: float,
    direction: str,
    risk: RiskConfig,
    pip_size: float = 0.0001,
) -> tuple[float | None, float | None]:
    """
    Compute stop-loss and take-profit price levels.
    direction: "buy" or "sell"
    Returns (stop_loss_price, take_profit_price) or (None, None) if not configured.
    """
    sl_pips = risk.stop_loss_pips
    tp_pips = risk.take_profit_pips
    if sl_pips is None and tp_pips is None:
        return None, None

    if direction == "buy":
        sl = (entry_price - sl_pips * pip_size) if sl_pips else None
        tp = (entry_price + tp_pips * pip_size) if tp_pips else None
    else:
        sl = (entry_price + sl_pips * pip_size) if sl_pips else None
        tp = (entry_price - tp_pips * pip_size) if tp_pips else None

    return sl, tp


def check_position_limit(risk: RiskConfig, open_positions: int) -> bool:
    """Return True if a new position can be opened."""
    return open_positions < risk.max_open_positions


def _clamp_lot(raw: float, max_lot: float) -> float:
    return round(min(max(raw, 0.01), max_lot), 2)

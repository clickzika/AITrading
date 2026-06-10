from __future__ import annotations

import os
os.environ.setdefault("MT5_MOCK", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("TRADER_PASSWORD", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("REDIS_PASSWORD", "test")

import pytest

from app.services.strategy.engine import (
    StrategyLoadError,
    evaluate_conditions,
    evaluate_entry,
    load_strategy,
)
from app.services.strategy.models import (
    ConditionLogicEnum,
    RiskMethodEnum,
    StrategyConfig,
)
from app.services.strategy.risk import (
    DailyLossTracker,
    calculate_lot_size,
    calculate_martingale_lot,
    check_position_limit,
    compute_sl_tp,
)


# ── load_strategy ────────────────────────────────────────────────────────────


def test_load_strategy_ema_macd(tmp_path):
    yml = tmp_path / "test_strat.yml"
    yml.write_text("""
strategy: test_strat
symbol: XAUUSD
timeframe: H1
entry:
  conditions:
    - type: ema_cross
      fast: 20
      slow: 50
      direction: bullish
  logic: AND
risk:
  method: fixed_fractional
  risk_pct: 1.0
  stop_loss_pips: 30
  take_profit_pips: 90
  max_daily_loss_usd: 200
  max_open_positions: 3
  max_lot_size: 1.0
""")
    cfg = load_strategy(str(yml))
    assert cfg.strategy == "test_strat"
    assert cfg.symbol == "XAUUSD"
    assert cfg.risk.method == RiskMethodEnum.FIXED_FRACTIONAL
    assert cfg.risk.risk_pct == 1.0
    assert cfg.entry is not None
    assert len(cfg.entry.conditions) == 1


def test_load_strategy_missing_file():
    from app.services.strategy.engine import StrategyLoadError
    with pytest.raises(StrategyLoadError, match="not found"):
        load_strategy("nonexistent_strategy_xyz")


def test_load_strategy_martingale_requires_max_multiplier(tmp_path):
    from app.services.strategy.engine import StrategyLoadError
    yml = tmp_path / "bad_martingale.yml"
    yml.write_text("""
strategy: bad_mart
symbol: XAUUSD
timeframe: H1
entry:
  conditions:
    - type: price_above
      level: 2300
  logic: AND
risk:
  method: martingale
  lot_size: 0.01
  max_daily_loss_usd: 100
  max_lot_size: 1.0
""")
    with pytest.raises(StrategyLoadError, match="max_multiplier"):
        load_strategy(str(yml))


def test_load_strategy_grid_type(tmp_path):
    yml = tmp_path / "grid_test.yml"
    yml.write_text("""
strategy: grid_test
symbol: BTCUSD
timeframe: H1
type: grid
grid:
  direction: both
  levels: 5
  spacing_usd: 100
  base_lot: 0.01
risk:
  method: fixed_lot
  lot_size: 0.01
  max_daily_loss_usd: 100
  max_open_positions: 10
  max_lot_size: 0.1
""")
    cfg = load_strategy(str(yml))
    assert cfg.grid is not None
    assert cfg.grid.levels == 5


# ── evaluate_conditions ──────────────────────────────────────────────────────


def test_and_logic_all_true():
    assert evaluate_conditions([True, True, True], ConditionLogicEnum.AND) is True


def test_and_logic_one_false():
    assert evaluate_conditions([True, False, True], ConditionLogicEnum.AND) is False


def test_or_logic_one_true():
    assert evaluate_conditions([False, True, False], ConditionLogicEnum.OR) is True


def test_or_logic_all_false():
    assert evaluate_conditions([False, False], ConditionLogicEnum.OR) is False


def test_empty_conditions_returns_false():
    assert evaluate_conditions([], ConditionLogicEnum.AND) is False


# ── evaluate_entry condition types ──────────────────────────────────────────


def _make_ema_cross_config(tmp_path, direction="bullish"):
    yml = tmp_path / "strat.yml"
    yml.write_text(f"""
strategy: test
symbol: XAUUSD
timeframe: H1
entry:
  conditions:
    - type: ema_cross
      fast: 20
      slow: 50
      direction: {direction}
  logic: AND
risk:
  method: fixed_lot
  lot_size: 0.1
  max_daily_loss_usd: 100
  max_open_positions: 2
  max_lot_size: 1.0
""")
    return load_strategy(str(yml))


def test_ema_cross_bullish_fires(tmp_path):
    cfg = _make_ema_cross_config(tmp_path, "bullish")
    # fast crosses above slow: was below, now above
    data = {"ema": {"20": [2300.0, 2305.0], "50": [2302.0, 2303.0]}}
    assert evaluate_entry(cfg, data) is True


def test_ema_cross_bullish_no_cross(tmp_path):
    cfg = _make_ema_cross_config(tmp_path, "bullish")
    data = {"ema": {"20": [2300.0, 2301.0], "50": [2302.0, 2303.0]}}
    assert evaluate_entry(cfg, data) is False


# ── risk manager ─────────────────────────────────────────────────────────────


def _make_risk(method="fixed_fractional", **kwargs):
    from app.services.strategy.models import RiskConfig
    base = {
        "method": method,
        "risk_pct": 1.0,
        "stop_loss_pips": 30,
        "take_profit_pips": 90,
        "max_daily_loss_usd": 200,
        "max_open_positions": 3,
        "max_lot_size": 2.0,
    }
    base.update(kwargs)
    return RiskConfig(**base)


def test_fixed_fractional_lot_size():
    risk = _make_risk("fixed_fractional", risk_pct=1.0, stop_loss_pips=30)
    # 1% of 10000 = 100 USD risk; 30 pips * 10 USD/pip = 300 → 100/300 ≈ 0.33
    lot = calculate_lot_size(risk, account_balance=10_000, pip_value=10.0)
    assert 0.30 <= lot <= 0.40


def test_fixed_lot():
    risk = _make_risk("fixed_lot", lot_size=0.5)
    lot = calculate_lot_size(risk, account_balance=10_000)
    assert lot == 0.5


def test_lot_clamped_to_max():
    risk = _make_risk("fixed_fractional", risk_pct=100.0, max_lot_size=1.0)
    lot = calculate_lot_size(risk, account_balance=100_000)
    assert lot == 1.0


def test_martingale_lot_doubles():
    risk = _make_risk(
        "martingale",
        lot_size=0.1,
        max_multiplier=16.0,
        multiplier=2.0,
        max_lot_size=2.0,
    )
    assert calculate_martingale_lot(risk, 0.1, 0) == 0.1
    assert calculate_martingale_lot(risk, 0.1, 1) == 0.2
    assert calculate_martingale_lot(risk, 0.1, 2) == 0.4


def test_martingale_capped_at_max_multiplier():
    risk = _make_risk(
        "martingale",
        lot_size=0.1,
        max_multiplier=4.0,
        multiplier=2.0,
        max_lot_size=2.0,
    )
    # 2^10 = 1024 but max_multiplier = 4 → 0.1 * 4 = 0.4
    assert calculate_martingale_lot(risk, 0.1, 10) == 0.4


def test_sl_tp_buy():
    risk = _make_risk(stop_loss_pips=30, take_profit_pips=90)
    sl, tp = compute_sl_tp(2300.0, "buy", risk, pip_size=0.1)
    assert sl == pytest.approx(2300.0 - 30 * 0.1)
    assert tp == pytest.approx(2300.0 + 90 * 0.1)


def test_sl_tp_sell():
    risk = _make_risk(stop_loss_pips=30, take_profit_pips=90)
    sl, tp = compute_sl_tp(2300.0, "sell", risk, pip_size=0.1)
    assert sl == pytest.approx(2300.0 + 30 * 0.1)
    assert tp == pytest.approx(2300.0 - 90 * 0.1)


def test_daily_loss_tracker():
    tracker = DailyLossTracker(max_loss_usd=200.0)
    assert not tracker.is_breached
    tracker.record_loss(150.0)
    assert not tracker.is_breached
    tracker.record_loss(60.0)
    assert tracker.is_breached
    assert tracker.remaining_usd == 0.0


def test_position_limit():
    risk = _make_risk(max_open_positions=3)
    assert check_position_limit(risk, 2) is True
    assert check_position_limit(risk, 3) is False

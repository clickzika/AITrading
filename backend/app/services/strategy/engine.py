from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.services.strategy.models import ConditionLogicEnum, StrategyConfig


_STRATEGIES_DIR = Path(__file__).parent.parent.parent.parent / "strategies"


class StrategyLoadError(Exception):
    pass


def load_strategy(name_or_path: str) -> StrategyConfig:
    """
    Load and validate a strategy from a YAML file.
    Accepts either a bare name (looks in strategies/) or a full path.
    Raises StrategyLoadError on any parse or validation failure.
    """
    path = Path(name_or_path)
    if not path.is_absolute() and not path.exists():
        path = _STRATEGIES_DIR / f"{name_or_path}.yml"
        if not path.exists():
            path = _STRATEGIES_DIR / f"{name_or_path}.yaml"

    if not path.exists():
        raise StrategyLoadError(f"Strategy file not found: {name_or_path}")

    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise StrategyLoadError(f"YAML parse error in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise StrategyLoadError(f"Strategy file must be a YAML mapping: {path}")

    try:
        return StrategyConfig(**raw)
    except ValidationError as exc:
        raise StrategyLoadError(f"Validation error in {path}:\n{exc}") from exc


def load_all_strategies(directory: str | Path | None = None) -> dict[str, StrategyConfig]:
    """Load all .yml/.yaml files from strategies directory. Skips invalid files with a warning."""
    import logging

    log = logging.getLogger(__name__)
    base = Path(directory) if directory else _STRATEGIES_DIR
    strategies: dict[str, StrategyConfig] = {}

    for yml_file in sorted(base.glob("*.yml")) + sorted(base.glob("*.yaml")):
        try:
            cfg = load_strategy(str(yml_file))
            strategies[cfg.strategy] = cfg
        except StrategyLoadError as exc:
            log.warning("Skipping invalid strategy %s: %s", yml_file.name, exc)

    return strategies


def evaluate_conditions(
    conditions_result: list[bool],
    logic: ConditionLogicEnum,
) -> bool:
    """Combine boolean results from individual condition checks per AND/OR logic."""
    if not conditions_result:
        return False
    if logic == ConditionLogicEnum.AND:
        return all(conditions_result)
    return any(conditions_result)


def evaluate_entry(strategy: StrategyConfig, market_data: dict[str, Any]) -> bool:
    """
    Evaluate all entry conditions against current market_data.
    market_data keys: symbol, timeframe, ema, macd, fib, order_blocks, fvg, bos_choch, etc.
    Returns True if entry signal is active.
    """
    if strategy.entry is None:
        return False

    results = [
        _eval_condition(cond.type, cond.params, market_data)
        for cond in strategy.entry.conditions
    ]
    return evaluate_conditions(results, strategy.entry.logic)


def evaluate_exit(strategy: StrategyConfig, market_data: dict[str, Any]) -> bool:
    """Evaluate exit conditions. Returns True if exit signal is active."""
    if strategy.exit is None:
        return False

    results = [
        _eval_condition(cond.type, cond.params, market_data)
        for cond in strategy.exit.conditions
    ]
    return evaluate_conditions(results, strategy.exit.logic)


def _eval_condition(condition_type: str, params: dict[str, Any], market_data: dict[str, Any]) -> bool:
    """Dispatch a single condition to its evaluator. Returns False on unknown type (safe default)."""
    evaluators = {
        "ema_cross": _eval_ema_cross,
        "macd_signal": _eval_macd_signal,
        "fib_zone": _eval_fib_zone,
        "order_block": _eval_order_block,
        "fvg": _eval_fvg,
        "bos": _eval_bos,
        "choch": _eval_choch,
        "price_above": _eval_price_above,
        "price_below": _eval_price_below,
        "liquidity_sweep": _eval_liquidity_sweep,
    }
    evaluator = evaluators.get(condition_type)
    if evaluator is None:
        import logging
        logging.getLogger(__name__).warning("Unknown condition type: %s", condition_type)
        return False
    return evaluator(params, market_data)


# ── individual condition evaluators ─────────────────────────────────────────


def _eval_ema_cross(params: dict[str, Any], data: dict[str, Any]) -> bool:
    fast = params.get("fast", 20)
    slow = params.get("slow", 50)
    direction = params.get("direction", "bullish")
    ema = data.get("ema", {})

    fast_vals = ema.get(str(fast)) or ema.get(fast)
    slow_vals = ema.get(str(slow)) or ema.get(slow)
    if not fast_vals or not slow_vals or len(fast_vals) < 2 or len(slow_vals) < 2:
        return False

    if direction == "bullish":
        return fast_vals[-2] <= slow_vals[-2] and fast_vals[-1] > slow_vals[-1]
    elif direction == "bearish":
        return fast_vals[-2] >= slow_vals[-2] and fast_vals[-1] < slow_vals[-1]
    return False


def _eval_macd_signal(params: dict[str, Any], data: dict[str, Any]) -> bool:
    expected = params.get("signal", "bullish")
    macd_signal = data.get("macd_signal")
    if macd_signal is None:
        return False
    if expected == "bullish":
        return macd_signal in ("bullish_cross", "bullish")
    elif expected == "bearish":
        return macd_signal in ("bearish_cross", "bearish")
    return macd_signal == expected


def _eval_fib_zone(params: dict[str, Any], data: dict[str, Any]) -> bool:
    levels = params.get("levels", [38.2, 61.8])
    zone_type = params.get("zone", "support")
    fib = data.get("fib_retracement", {})
    current_price = data.get("price")
    if not fib or current_price is None:
        return False

    tolerance = data.get("fib_tolerance_pips", 5) * data.get("pip_size", 0.0001)
    for level in levels:
        level_price = fib.get(str(level)) or fib.get(level)
        if level_price is None:
            continue
        if abs(current_price - level_price) <= tolerance:
            if zone_type == "support" and current_price >= level_price:
                return True
            if zone_type == "resistance" and current_price <= level_price:
                return True
    return False


def _eval_order_block(params: dict[str, Any], data: dict[str, Any]) -> bool:
    direction = params.get("direction", "bullish")
    mitigated = params.get("mitigated", False)
    price = data.get("price")
    obs = data.get("order_blocks", [])
    if price is None:
        return False

    for ob in obs:
        if ob.get("type") != direction:
            continue
        if ob.get("mitigated", False) != mitigated:
            continue
        if ob["bottom"] <= price <= ob["top"]:
            return True
    return False


def _eval_fvg(params: dict[str, Any], data: dict[str, Any]) -> bool:
    direction = params.get("direction", "bullish")
    filled = params.get("filled", False)
    price = data.get("price")
    fvgs = data.get("fvg", [])
    if price is None:
        return False

    for fvg in fvgs:
        if fvg.get("type") != direction:
            continue
        if fvg.get("filled", True) != filled:
            continue
        if fvg["bottom"] <= price <= fvg["top"]:
            return True
    return False


def _eval_bos(params: dict[str, Any], data: dict[str, Any]) -> bool:
    direction = params.get("direction", "bullish")
    events = data.get("bos_choch", [])
    return any(e["type"] == "BOS" and e["direction"] == direction for e in events)


def _eval_choch(params: dict[str, Any], data: dict[str, Any]) -> bool:
    direction = params.get("direction", "bullish")
    events = data.get("bos_choch", [])
    return any(e["type"] == "ChoCH" and e["direction"] == direction for e in events)


def _eval_price_above(params: dict[str, Any], data: dict[str, Any]) -> bool:
    level = params.get("level")
    price = data.get("price")
    if level is None or price is None:
        return False
    return price > level


def _eval_price_below(params: dict[str, Any], data: dict[str, Any]) -> bool:
    level = params.get("level")
    price = data.get("price")
    if level is None or price is None:
        return False
    return price < level


def _eval_liquidity_sweep(params: dict[str, Any], data: dict[str, Any]) -> bool:
    sweep_type = params.get("type", "SSL")
    sweeps = data.get("liquidity_sweeps", [])
    return any(s["type"] == sweep_type for s in sweeps)

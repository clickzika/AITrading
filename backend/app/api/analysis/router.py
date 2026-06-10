from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.middleware.auth import get_current_user
from app.services.analysis.fibonacci import compute_retracement, compute_extension
from app.services.analysis.indicators import compute_ema, compute_macd
from app.services.analysis.volume_profile import compute_vpvr
from app.services.analysis.candle_patterns import detect_patterns
from app.services.analysis.wick_analysis import detect_wick_fills, detect_sl_sweeps
from app.services.smc.order_blocks import detect_order_blocks
from app.services.smc.fvg import detect_fvg
from app.services.smc.bos_choch import detect_bos_choch
from app.services.smc.liquidity import detect_sweeps
from app.services.smc.zones import detect_demand_supply_zones, detect_sr_zones
from app.services.market_data.ohlcv_store import OHLCVStore

log = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


def _get_store() -> OHLCVStore:
    return OHLCVStore()


@router.get("/indicators/{symbol}")
async def get_indicators(
    symbol: str,
    timeframe: str = Query(default="H1"),
    limit: int = Query(default=200, ge=50, le=1000),
    _: str = Depends(get_current_user),
    store: OHLCVStore = Depends(_get_store),
) -> dict[str, Any]:
    """EMA (20/50/200) and MACD for a symbol."""
    df = await store.get_candles(symbol.upper(), timeframe, limit=limit)
    if df is None or len(df) < 26:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insufficient data")

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "ema": compute_ema(df),
        "macd": compute_macd(df),
    }


@router.get("/fibonacci/{symbol}")
async def get_fibonacci(
    symbol: str,
    timeframe: str = Query(default="H1"),
    direction: str = Query(default="bullish", pattern=r"^(bullish|bearish)$"),
    limit: int = Query(default=100, ge=20, le=500),
    _: str = Depends(get_current_user),
    store: OHLCVStore = Depends(_get_store),
) -> dict[str, Any]:
    """Fibonacci retracement and extension for latest swing."""
    df = await store.get_candles(symbol.upper(), timeframe, limit=limit)
    if df is None or len(df) < 10:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insufficient data")

    swing_high = float(df["high"].max())
    swing_low = float(df["low"].min())

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "swing_high": swing_high,
        "swing_low": swing_low,
        "retracement": compute_retracement(swing_high, swing_low, direction),
        "extension": compute_extension(swing_high, swing_low, direction),
    }


@router.get("/smc/{symbol}")
async def get_smc(
    symbol: str,
    timeframe: str = Query(default="H1"),
    limit: int = Query(default=200, ge=50, le=1000),
    _: str = Depends(get_current_user),
    store: OHLCVStore = Depends(_get_store),
) -> dict[str, Any]:
    """Full SMC analysis: OB, FVG, BOS/ChoCH, liquidity sweeps, zones."""
    df = await store.get_candles(symbol.upper(), timeframe, limit=limit)
    if df is None or len(df) < 20:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insufficient data")

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "order_blocks": detect_order_blocks(df),
        "fvg": detect_fvg(df),
        "bos_choch": detect_bos_choch(df),
        "liquidity_sweeps": detect_sweeps(df),
        "zones": detect_demand_supply_zones(df),
        "sr_zones": detect_sr_zones(df),
    }


@router.get("/volume-profile/{symbol}")
async def get_volume_profile(
    symbol: str,
    timeframe: str = Query(default="H1"),
    limit: int = Query(default=200, ge=50, le=1000),
    rows: int = Query(default=24, ge=10, le=100),
    _: str = Depends(get_current_user),
    store: OHLCVStore = Depends(_get_store),
) -> dict[str, Any]:
    """Volume Profile (VPVR) with POC, VAH, VAL."""
    df = await store.get_candles(symbol.upper(), timeframe, limit=limit)
    if df is None or len(df) < 10:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insufficient data")

    vp = compute_vpvr(df, rows=rows)
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "poc": vp.poc,
        "vah": vp.vah,
        "val": vp.val,
        "value_area_pct": vp.value_area_pct,
        "rows": vp.rows,
    }


@router.get("/candle-patterns/{symbol}")
async def get_candle_patterns(
    symbol: str,
    timeframe: str = Query(default="H1"),
    limit: int = Query(default=50, ge=10, le=200),
    _: str = Depends(get_current_user),
    store: OHLCVStore = Depends(_get_store),
) -> dict[str, Any]:
    """Candlestick pattern recognition."""
    df = await store.get_candles(symbol.upper(), timeframe, limit=limit)
    if df is None or len(df) < 5:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insufficient data")

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "patterns": detect_patterns(df),
    }


@router.get("/wick-analysis/{symbol}")
async def get_wick_analysis(
    symbol: str,
    timeframe: str = Query(default="H1"),
    limit: int = Query(default=100, ge=20, le=500),
    _: str = Depends(get_current_user),
    store: OHLCVStore = Depends(_get_store),
) -> dict[str, Any]:
    """Wick fills and stop-loss sweep detection."""
    df = await store.get_candles(symbol.upper(), timeframe, limit=limit)
    if df is None or len(df) < 10:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insufficient data")

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "wick_fills": detect_wick_fills(df),
        "sl_sweeps": detect_sl_sweeps(df),
    }

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/trades", tags=["trades"])


class TradeResponse(BaseModel):
    id: str
    symbol: str
    direction: str
    lot_size: float
    open_price: float
    close_price: float | None
    stop_loss: float | None
    take_profit: float | None
    profit: float | None
    status: str
    strategy: str | None
    mt5_ticket: int | None
    opened_at: str
    closed_at: str | None


@router.get("", response_model=list[TradeResponse])
async def list_trades(
    symbol: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: str = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Trade history log with filter and pagination."""
    return []


@router.get("/positions")
async def get_open_positions(_: str = Depends(get_current_user)) -> dict[str, Any]:
    """Current open positions from MT5."""
    try:
        from app.services.execution.mt5_client import MT5Client
        from app.config.settings import settings
        from app.services.execution.position_manager import PositionManager

        if settings.mt5_mock:
            return {"positions": [], "total_profit": 0.0, "count": 0}

        client = MT5Client(
            login=settings.mt5_login,
            password=settings.mt5_password,
            server=settings.mt5_server,
        )
        pm = PositionManager(client)
        positions = pm.get_open_positions()
        return {
            "positions": [
                {
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "direction": p.direction,
                    "lot_size": p.lot_size,
                    "open_price": p.open_price,
                    "current_price": p.current_price,
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                    "profit": p.profit,
                }
                for p in positions
            ],
            "total_profit": pm.get_total_profit(),
            "count": len(positions),
        }
    except Exception as exc:
        log.error("Failed to fetch positions: %s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MT5 unavailable")


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(trade_id: str, _: str = Depends(get_current_user)) -> dict[str, Any]:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")

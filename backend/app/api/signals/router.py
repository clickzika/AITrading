from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/signals", tags=["signals"])


class SignalResponse(BaseModel):
    id: str
    symbol: str
    action: str
    source: str
    price: float | None
    strategy: str | None
    created_at: str
    status: str


@router.get("", response_model=list[SignalResponse])
async def list_signals(
    symbol: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: str = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List recent trading signals (TradingView + strategy engine)."""
    # Placeholder: returns empty list until DB repository is wired
    return []


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: str,
    _: str = Depends(get_current_user),
) -> dict[str, Any]:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")

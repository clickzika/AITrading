from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class OrderType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    BUY_LIMIT = "buy_limit"
    SELL_LIMIT = "sell_limit"
    BUY_STOP = "buy_stop"
    SELL_STOP = "sell_stop"


@dataclass
class OrderIntent:
    """
    Represents an order intent BEFORE it is sent to MT5.
    Must be persisted to DB (status=PENDING) before MT5 execution call.
    """
    symbol: str
    order_type: OrderType
    lot_size: float
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    comment: str = ""
    strategy: str = ""
    magic: int = 0
    db_id: str | None = None  # set after DB write
    mt5_ticket: int | None = None
    status: OrderStatus = OrderStatus.PENDING


@dataclass
class OrderResult:
    success: bool
    mt5_ticket: int | None = None
    retcode: int | None = None
    comment: str = ""
    volume: float | None = None
    price: float | None = None


class OrderManager:
    """
    Manages order lifecycle: intent creation, DB write, MT5 send, status tracking.
    Enforces: DB write before MT5 call — audit trail cannot be skipped.
    """

    def __init__(self, mt5_client: Any, repository: Any | None = None) -> None:
        self._mt5 = mt5_client
        self._repo = repository  # optional DB repository for audit trail

    async def place_order(self, intent: OrderIntent) -> OrderResult:
        """
        Full order pipeline:
        1. Persist intent to DB (PENDING) — audit trail
        2. Send to MT5
        3. Update DB with result (FILLED or REJECTED)
        """
        # Step 1: DB write BEFORE MT5 call (mandatory audit trail)
        if self._repo is not None:
            intent.db_id = await self._repo.create_order(intent)

        # Step 2: MT5 send
        request = self._build_mt5_request(intent)
        raw_result = self._mt5.order_send(request)
        result = self._parse_result(raw_result)

        # Step 3: Update DB with outcome
        if result.success:
            intent.status = OrderStatus.FILLED
            intent.mt5_ticket = result.mt5_ticket
        else:
            intent.status = OrderStatus.REJECTED
            log.warning(
                "Order rejected: symbol=%s type=%s retcode=%s comment=%s",
                intent.symbol, intent.order_type, result.retcode, result.comment,
            )

        if self._repo is not None and intent.db_id:
            await self._repo.update_order_status(
                intent.db_id,
                status=intent.status,
                mt5_ticket=intent.mt5_ticket,
                retcode=result.retcode,
            )

        return result

    async def cancel_order(self, ticket: int) -> bool:
        """Cancel a pending MT5 order by ticket number."""
        request = {
            "action": 8,  # TRADE_ACTION_REMOVE
            "order": ticket,
        }
        raw = self._mt5.order_send(request)
        return raw.get("retcode") == 10009

    def _build_mt5_request(self, intent: OrderIntent) -> dict[str, Any]:
        action_map = {
            OrderType.BUY: 1,       # TRADE_ACTION_DEAL
            OrderType.SELL: 1,
            OrderType.BUY_LIMIT: 5,  # TRADE_ACTION_PENDING
            OrderType.SELL_LIMIT: 5,
            OrderType.BUY_STOP: 5,
            OrderType.SELL_STOP: 5,
        }
        order_type_map = {
            OrderType.BUY: 0,
            OrderType.SELL: 1,
            OrderType.BUY_LIMIT: 2,
            OrderType.SELL_LIMIT: 3,
            OrderType.BUY_STOP: 4,
            OrderType.SELL_STOP: 5,
        }
        req: dict[str, Any] = {
            "action": action_map[intent.order_type],
            "symbol": intent.symbol,
            "volume": intent.lot_size,
            "type": order_type_map[intent.order_type],
            "deviation": 10,
            "magic": intent.magic,
            "comment": intent.comment[:31] if intent.comment else "",
            "type_time": 0,  # GTC
            "type_filling": 1,  # IOC
        }
        if intent.price is not None:
            req["price"] = intent.price
        if intent.stop_loss is not None:
            req["sl"] = intent.stop_loss
        if intent.take_profit is not None:
            req["tp"] = intent.take_profit
        return req

    @staticmethod
    def _parse_result(raw: dict[str, Any]) -> OrderResult:
        retcode = raw.get("retcode")
        success = retcode == 10009
        return OrderResult(
            success=success,
            mt5_ticket=raw.get("order") or raw.get("deal"),
            retcode=retcode,
            comment=raw.get("comment", ""),
            volume=raw.get("volume"),
            price=raw.get("price"),
        )

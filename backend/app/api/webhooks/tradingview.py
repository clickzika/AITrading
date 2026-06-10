from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.config.settings import settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhooks"])


class TradingViewSignal(BaseModel):
    """Parsed TradingView alert payload."""
    symbol: str = Field(min_length=1, max_length=20)
    action: str = Field(pattern=r"^(buy|sell|close_buy|close_sell|close_all)$")
    price: float | None = None
    timeframe: str | None = None
    strategy: str | None = None
    comment: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


def _verify_signature(body: bytes, signature: str | None) -> None:
    """
    Verify TradingView webhook signature using HMAC-SHA256.
    Uses constant-time comparison to prevent timing attacks.
    Raises 401 if secret is configured and signature is invalid/missing.
    """
    secret = settings.tradingview_webhook_secret
    if not secret:
        return  # no secret configured — skip verification (dev mode)

    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Webhook-Signature header",
        )

    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    provided = signature.removeprefix("sha256=")

    if not hmac.compare_digest(expected, provided):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )


@router.post("/tradingview", status_code=status.HTTP_200_OK)
async def tradingview_webhook(
    request: Request,
    x_webhook_signature: str | None = Header(default=None),
) -> dict[str, str]:
    """
    Receive TradingView alert webhooks.
    Payload can be JSON with {symbol, action, price, ...} fields.
    Verifies HMAC-SHA256 signature when TRADINGVIEW_WEBHOOK_SECRET is set.
    """
    raw_body = await request.body()
    _verify_signature(raw_body, x_webhook_signature)

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid JSON payload: {exc}",
        ) from exc

    # Normalize symbol to uppercase
    if "symbol" in payload:
        payload["symbol"] = str(payload["symbol"]).upper().strip()

    try:
        signal = TradingViewSignal(**payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Payload validation failed: {exc}",
        ) from exc

    log.info(
        "TradingView signal received: symbol=%s action=%s price=%s strategy=%s",
        signal.symbol,
        signal.action,
        signal.price,
        signal.strategy,
    )

    # Publish to Redis for downstream consumers
    await _publish_signal(signal)

    return {"status": "accepted", "symbol": signal.symbol, "action": signal.action}


async def _publish_signal(signal: TradingViewSignal) -> None:
    """Publish validated signal to Redis pub/sub channel."""
    try:
        from app.config.settings import settings as s
        import redis.asyncio as aioredis  # type: ignore[import-untyped]

        client = aioredis.from_url(s.redis_url, decode_responses=True)
        channel = f"signal:tradingview:{signal.symbol}"
        payload = signal.model_dump_json()
        await client.publish(channel, payload)
        await client.aclose()
    except Exception as exc:
        # Non-fatal: log warning but don't fail the webhook response
        log.warning("Failed to publish signal to Redis: %s", exc)

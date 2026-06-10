from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import redis.asyncio as aioredis  # type: ignore[import-untyped]
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.config.settings import settings
from app.middleware.auth import decode_token

log = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

_SUBSCRIPTIONS = {
    "prices": "price:*",
    "candles": "candle:*",
    "signals": "signal:*",
    "positions": "position:*",
}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for live price, candle, signal, and position updates.
    Client must authenticate with JWT via query param ?token=<jwt> or first message.
    Protocol: JSON messages.
      Client sends: {"subscribe": ["prices", "candles", "signals"]}
      Server sends: {"type": "price", "symbol": "XAUUSD", "bid": ..., "ask": ...}
    """
    await websocket.accept()

    # Authenticate via query param first
    token = websocket.query_params.get("token")
    if not token:
        try:
            msg = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            data = json.loads(msg)
            token = data.get("token")
        except (asyncio.TimeoutError, json.JSONDecodeError, Exception):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    if not token or not decode_token(token):
        await websocket.send_json({"error": "unauthorized"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Wait for subscription request
    subscriptions: set[str] = {"prices", "signals"}
    try:
        sub_msg = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        sub_data = json.loads(sub_msg)
        if "subscribe" in sub_data:
            subscriptions = set(sub_data["subscribe"]) & set(_SUBSCRIPTIONS.keys())
    except (asyncio.TimeoutError, json.JSONDecodeError):
        pass  # use defaults

    channels = [_SUBSCRIPTIONS[s] for s in subscriptions]
    log.info("WebSocket client subscribed to: %s", subscriptions)

    try:
        await _stream_redis(websocket, channels)
    except WebSocketDisconnect:
        log.info("WebSocket client disconnected")


async def _stream_redis(websocket: WebSocket, channel_patterns: list[str]) -> None:
    """Subscribe to Redis pub/sub patterns and forward messages to WebSocket."""
    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = client.pubsub()

        for pattern in channel_patterns:
            await pubsub.psubscribe(pattern)

        async def _listen() -> None:
            async for message in pubsub.listen():
                if message["type"] not in ("pmessage", "message"):
                    continue
                try:
                    payload = json.loads(message["data"])
                    await websocket.send_json(payload)
                except (json.JSONDecodeError, Exception):
                    pass

        # Run listener and heartbeat concurrently
        listener_task = asyncio.create_task(_listen())
        heartbeat_task = asyncio.create_task(_heartbeat(websocket))

        done, pending = await asyncio.wait(
            [listener_task, heartbeat_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()

    finally:
        await pubsub.aclose()
        await client.aclose()


async def _heartbeat(websocket: WebSocket, interval: float = 30.0) -> None:
    """Send periodic ping to keep the connection alive."""
    while True:
        await asyncio.sleep(interval)
        try:
            await websocket.send_json({"type": "ping"})
        except Exception:
            break

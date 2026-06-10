from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.middleware.auth import get_current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])


class ChatMessage(BaseModel):
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    stream: bool = False


def _get_copilot() -> Any:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claude AI co-pilot not configured (missing ANTHROPIC_API_KEY)",
        )
    from app.services.ai.copilot import CopilotService
    return CopilotService(api_key=settings.anthropic_api_key)


@router.post("/chat")
async def chat(
    request: ChatRequest,
    _: str = Depends(get_current_user),
) -> Any:
    """
    Claude AI co-pilot chat endpoint.
    Supports streaming (SSE) via stream=true in request body.
    """
    copilot = _get_copilot()
    messages = [m.model_dump() for m in request.messages]

    if request.stream:
        return StreamingResponse(
            _stream_chat(copilot, messages),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        text = copilot.chat(messages)
        return {"role": "assistant", "content": text}
    except Exception as exc:
        log.error("Copilot chat error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service error",
        ) from exc


async def _stream_chat(copilot: Any, messages: list[dict[str, str]]) -> AsyncIterator[str]:
    """Yield SSE events from Claude streaming response."""
    try:
        with copilot.stream_chat(messages) as stream:
            for text in stream.text_stream:
                data = json.dumps({"type": "text", "text": text})
                yield f"data: {data}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"
    except Exception as exc:
        log.error("Copilot stream error: %s", exc)
        error_data = json.dumps({"type": "error", "message": "Stream error"})
        yield f"data: {error_data}\n\n"


@router.post("/report/{symbol}")
async def generate_report(
    symbol: str,
    _: str = Depends(get_current_user),
) -> dict[str, str]:
    """
    Generate a Claude AI market analysis report for a symbol.
    Fetches current analysis data and sends to co-pilot.
    """
    copilot = _get_copilot()
    symbol_upper = symbol.upper()

    # Gather analysis data (best-effort — skip if services unavailable)
    analysis: dict[str, Any] = {"symbol": symbol_upper}
    try:
        from app.services.market_data.ohlcv_store import OHLCVStore
        from app.services.smc.order_blocks import detect_order_blocks
        from app.services.smc.fvg import detect_fvg
        from app.services.smc.bos_choch import detect_bos_choch
        from app.services.analysis.indicators import compute_macd, get_macd_signal

        store = OHLCVStore()
        df = await store.get_candles(symbol_upper, "H1", limit=200)
        if df is not None and len(df) >= 26:
            macd = compute_macd(df)
            analysis["macd_signal"] = get_macd_signal(macd)
            analysis["order_blocks"] = detect_order_blocks(df)
            analysis["fvg"] = detect_fvg(df)
            analysis["bos_choch"] = detect_bos_choch(df)
    except Exception as exc:
        log.warning("Could not fetch analysis for report: %s", exc)

    try:
        report = copilot.generate_market_report(symbol_upper, analysis)
        return {"symbol": symbol_upper, "report": report}
    except Exception as exc:
        log.error("Report generation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI report generation failed",
        ) from exc

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an AI trading co-pilot for an algorithmic trading platform focused on XAUUSD, Forex, and Crypto.

You assist with:
- Market analysis: interpreting candlestick patterns, SMC concepts, indicators
- Strategy design: EMA/MACD, Fibonacci, Order Blocks, FVG, BOS/ChoCH
- Trade review: evaluating entry/exit rationale, risk/reward assessment
- Risk management: lot sizing, stop placement, Kelly Criterion
- Market context: explaining price action and SMC structure

Guidelines:
- Always emphasize risk management over profit potential
- Never give specific financial advice or guarantee results
- If asked about a live trade, ask for current price, SL, TP, and account risk %
- Keep responses concise and action-oriented
- Reference SMC concepts by their standard names (OB, FVG, BOS, ChoCH, SSL/BSL)"""


class CopilotService:
    """Claude AI co-pilot for market analysis and strategy consultation."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str = "claude-opus-4-8",
        max_tokens: int = 1024,
    ) -> str:
        """Single-turn chat. Returns complete response text."""
        client = self._get_client()
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=_SYSTEM_PROMPT,
            messages=messages,
        )
        return response.content[0].text

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str = "claude-opus-4-8",
        max_tokens: int = 1024,
    ) -> Any:
        """Streaming chat. Returns a context manager yielding text chunks."""
        client = self._get_client()
        return client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=_SYSTEM_PROMPT,
            messages=messages,
        )

    def generate_market_report(
        self,
        symbol: str,
        analysis: dict[str, Any],
        timeframes: list[str] | None = None,
    ) -> str:
        """
        Generate a structured daily market report for a given symbol.
        analysis: dict with keys like ema, macd, fib_retracement, order_blocks, etc.
        """
        tfs = ", ".join(timeframes or ["D1", "H4", "H1"])
        prompt = f"""Generate a concise market analysis report for {symbol}.

Timeframes analyzed: {tfs}

Technical data:
{_format_analysis(analysis)}

Structure the report as:
1. Trend Bias (1-2 sentences)
2. Key Levels (OBs, FVGs, S/R — top 3)
3. Trade Setup (entry trigger, SL placement, TP targets)
4. Risk Note (one sentence)

Keep it under 300 words."""

        return self.chat([{"role": "user", "content": prompt}])


def _format_analysis(analysis: dict[str, Any]) -> str:
    lines = []
    if "ema" in analysis:
        lines.append(f"EMA trend: {analysis.get('ema_trend', 'unknown')}")
    if "macd_signal" in analysis:
        lines.append(f"MACD signal: {analysis['macd_signal']}")
    if "order_blocks" in analysis:
        obs = analysis["order_blocks"]
        active = [o for o in obs if not o.get("mitigated")]
        lines.append(f"Active order blocks: {len(active)}")
    if "fvg" in analysis:
        unfilled = [f for f in analysis["fvg"] if not f.get("filled")]
        lines.append(f"Unfilled FVGs: {len(unfilled)}")
    if "bos_choch" in analysis:
        events = analysis["bos_choch"][-3:] if analysis["bos_choch"] else []
        lines.append(f"Recent BOS/ChoCH: {[e['type'] + ' ' + e['direction'] for e in events]}")
    return "\n".join(lines) if lines else "No analysis data provided"

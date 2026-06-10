from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)


class ImpactLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class NewsEvent:
    event_id: str
    title: str
    currency: str
    impact: ImpactLevel
    scheduled_utc: datetime
    actual: str | None = None
    forecast: str | None = None
    previous: str | None = None


@dataclass
class NewsFilter:
    """
    Configuration for news-based trading pauses.
    symbols: list of symbols affected (e.g. ["XAUUSD", "EURUSD"])
    currencies: if symbol contains this currency, apply the pause
    min_impact: minimum impact level to trigger a pause
    pause_minutes_before: minutes before event to pause trading
    pause_minutes_after: minutes after event to resume trading
    """
    symbols: list[str] = field(default_factory=list)
    currencies: list[str] = field(default_factory=list)
    min_impact: ImpactLevel = ImpactLevel.HIGH
    pause_minutes_before: int = 15
    pause_minutes_after: int = 15


class NewsCalendarService:
    """
    Tracks upcoming high-impact news events and determines whether
    trading should be paused for a given symbol.
    """

    _IMPACT_ORDER = {
        ImpactLevel.LOW: 0,
        ImpactLevel.MEDIUM: 1,
        ImpactLevel.HIGH: 2,
    }

    def __init__(self) -> None:
        self._events: list[NewsEvent] = []

    def load_events(self, events: list[dict[str, Any]]) -> None:
        """Load events from a list of dicts (e.g., from ForexFactory JSON feed)."""
        parsed: list[NewsEvent] = []
        for raw in events:
            try:
                parsed.append(NewsEvent(
                    event_id=str(raw.get("id", "")),
                    title=str(raw.get("title", "")),
                    currency=str(raw.get("currency", "")).upper(),
                    impact=ImpactLevel(raw.get("impact", "low").lower()),
                    scheduled_utc=datetime.fromisoformat(raw["scheduled_utc"]).replace(tzinfo=timezone.utc)
                    if "scheduled_utc" in raw
                    else datetime.now(timezone.utc),
                    actual=raw.get("actual"),
                    forecast=raw.get("forecast"),
                    previous=raw.get("previous"),
                ))
            except Exception as exc:
                log.warning("Skipping malformed event %s: %s", raw.get("id"), exc)
        self._events = parsed

    def should_pause_trading(
        self,
        symbol: str,
        news_filter: NewsFilter,
        now_utc: datetime | None = None,
    ) -> tuple[bool, str]:
        """
        Returns (should_pause, reason).
        Pauses trading if a relevant high-impact event is within the window.
        """
        now = now_utc or datetime.now(timezone.utc)
        symbol_upper = symbol.upper()

        min_impact_rank = self._IMPACT_ORDER[news_filter.min_impact]

        for event in self._events:
            if self._IMPACT_ORDER[event.impact] < min_impact_rank:
                continue

            if not self._affects_symbol(event.currency, symbol_upper, news_filter):
                continue

            delta_seconds = (event.scheduled_utc - now).total_seconds()
            pause_before_sec = news_filter.pause_minutes_before * 60
            pause_after_sec = news_filter.pause_minutes_after * 60

            if -pause_after_sec <= delta_seconds <= pause_before_sec:
                direction = "before" if delta_seconds >= 0 else "after"
                return (
                    True,
                    f"High-impact event '{event.title}' ({event.currency}) "
                    f"{abs(int(delta_seconds // 60))}min {direction}",
                )

        return False, ""

    def get_upcoming_events(
        self,
        symbol: str,
        news_filter: NewsFilter,
        now_utc: datetime | None = None,
        hours_ahead: int = 24,
    ) -> list[NewsEvent]:
        """Return events relevant to this symbol in the next N hours."""
        now = now_utc or datetime.now(timezone.utc)
        horizon_sec = hours_ahead * 3600
        symbol_upper = symbol.upper()
        min_impact_rank = self._IMPACT_ORDER[news_filter.min_impact]

        return [
            e for e in self._events
            if self._IMPACT_ORDER[e.impact] >= min_impact_rank
            and self._affects_symbol(e.currency, symbol_upper, news_filter)
            and 0 <= (e.scheduled_utc - now).total_seconds() <= horizon_sec
        ]

    def _affects_symbol(self, currency: str, symbol: str, news_filter: NewsFilter) -> bool:
        """True if this currency's events affect the given symbol."""
        if news_filter.symbols and symbol not in news_filter.symbols:
            return False
        if news_filter.currencies:
            return currency in news_filter.currencies
        # Default: check if the currency is part of the symbol name
        return currency in symbol

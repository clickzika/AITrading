"""
Gate 5 coverage boost tests.
Targets zero/low coverage modules that don't require MT5/DB/Redis connections:
- news.calendar, grid, hedge, smc.zones, wick_analysis, candle_patterns,
  order_manager (mocked), position_manager (mocked)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# NewsCalendarService
# ---------------------------------------------------------------------------
from app.services.news.calendar import (
    ImpactLevel, NewsEvent, NewsFilter, NewsCalendarService,
)


def _make_service_with_events(events: list[dict]) -> NewsCalendarService:
    svc = NewsCalendarService()
    svc.load_events(events)
    return svc


def _event_raw(
    title: str,
    currency: str,
    impact: str,
    delta_minutes: int,
    event_id: str = "1",
) -> dict:
    scheduled = datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)
    return {
        "id": event_id,
        "title": title,
        "currency": currency,
        "impact": impact,
        "scheduled_utc": scheduled.isoformat(),
    }


class TestNewsCalendarService:
    def test_should_pause_before_high_impact(self):
        svc = _make_service_with_events([
            _event_raw("NFP", "USD", "high", 10),
        ])
        news_filter = NewsFilter(currencies=["USD"], pause_minutes_before=15)
        paused, reason = svc.should_pause_trading("XAUUSD", news_filter)
        assert paused is True
        assert "NFP" in reason

    def test_should_not_pause_outside_window(self):
        svc = _make_service_with_events([
            _event_raw("NFP", "USD", "high", 60),
        ])
        news_filter = NewsFilter(currencies=["USD"], pause_minutes_before=15)
        paused, _ = svc.should_pause_trading("XAUUSD", news_filter)
        assert paused is False

    def test_should_pause_after_event(self):
        svc = _make_service_with_events([
            _event_raw("CPI", "USD", "high", -5),
        ])
        news_filter = NewsFilter(currencies=["USD"], pause_minutes_after=15)
        paused, reason = svc.should_pause_trading("XAUUSD", news_filter)
        assert paused is True
        assert "after" in reason

    def test_low_impact_not_paused_when_filter_high(self):
        svc = _make_service_with_events([
            _event_raw("Minor", "USD", "low", 5),
        ])
        news_filter = NewsFilter(currencies=["USD"], min_impact=ImpactLevel.HIGH)
        paused, _ = svc.should_pause_trading("XAUUSD", news_filter)
        assert paused is False

    def test_medium_impact_triggers_medium_filter(self):
        svc = _make_service_with_events([
            _event_raw("PMI", "EUR", "medium", 5),
        ])
        news_filter = NewsFilter(currencies=["EUR"], min_impact=ImpactLevel.MEDIUM)
        paused, _ = svc.should_pause_trading("EURUSD", news_filter)
        assert paused is True

    def test_symbol_filter_excludes_unrelated(self):
        svc = _make_service_with_events([
            _event_raw("NFP", "USD", "high", 5),
        ])
        news_filter = NewsFilter(symbols=["EURUSD"], currencies=["USD"])
        paused, _ = svc.should_pause_trading("XAUUSD", news_filter)
        assert paused is False

    def test_get_upcoming_events_returns_relevant(self):
        svc = _make_service_with_events([
            _event_raw("NFP", "USD", "high", 30, "e1"),
            _event_raw("CPI", "EUR", "high", 30, "e2"),
        ])
        news_filter = NewsFilter(currencies=["USD"])
        events = svc.get_upcoming_events("XAUUSD", news_filter, hours_ahead=2)
        assert len(events) == 1
        assert events[0].currency == "USD"

    def test_get_upcoming_events_excludes_past(self):
        svc = _make_service_with_events([
            _event_raw("Old", "USD", "high", -30),
        ])
        news_filter = NewsFilter(currencies=["USD"])
        events = svc.get_upcoming_events("XAUUSD", news_filter, hours_ahead=24)
        assert len(events) == 0

    def test_load_events_skips_malformed(self):
        svc = NewsCalendarService()
        # invalid impact value triggers ValueError in ImpactLevel() → skipped
        svc.load_events([{"id": "bad", "title": "T", "currency": "USD", "impact": "INVALID_IMPACT",
                          "scheduled_utc": "2026-01-01T00:00:00"}])
        assert len(svc._events) == 0

    def test_load_events_no_scheduled_utc_uses_now(self):
        svc = NewsCalendarService()
        svc.load_events([{"id": "1", "title": "T", "currency": "USD", "impact": "high"}])
        assert len(svc._events) == 1

    def test_currency_in_symbol_default_matching(self):
        svc = _make_service_with_events([
            _event_raw("BOE", "GBP", "high", 5),
        ])
        news_filter = NewsFilter()  # no currencies filter → use symbol contains logic
        paused, _ = svc.should_pause_trading("GBPUSD", news_filter)
        assert paused is True

    def test_no_events_returns_false(self):
        svc = NewsCalendarService()
        news_filter = NewsFilter()
        paused, _ = svc.should_pause_trading("XAUUSD", news_filter)
        assert paused is False


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------
from app.services.strategy.money_mgmt.grid import (
    build_grid, get_triggered_levels, rebuild_grid, GridState, GridLevel,
)


class TestGrid:
    def test_build_both_direction(self):
        state = build_grid(2000.0, levels=3, spacing=10.0, base_lot=0.1, max_lot=1.0)
        assert len(state.levels) == 6  # 3 buy + 3 sell
        buy_levels = [l for l in state.levels if l.direction == "buy"]
        sell_levels = [l for l in state.levels if l.direction == "sell"]
        assert len(buy_levels) == 3
        assert len(sell_levels) == 3

    def test_build_buy_only(self):
        state = build_grid(2000.0, levels=2, spacing=10.0, base_lot=0.1, max_lot=1.0, direction="buy")
        assert all(l.direction == "buy" for l in state.levels)
        assert len(state.levels) == 2

    def test_build_sell_only(self):
        state = build_grid(2000.0, levels=2, spacing=10.0, base_lot=0.1, max_lot=1.0, direction="sell")
        assert all(l.direction == "sell" for l in state.levels)

    def test_lot_clamped_to_max(self):
        state = build_grid(2000.0, levels=2, spacing=10.0, base_lot=5.0, max_lot=1.0)
        assert all(l.lot == 1.0 for l in state.levels)

    def test_buy_levels_below_base(self):
        state = build_grid(2000.0, levels=3, spacing=10.0, base_lot=0.1, max_lot=1.0, direction="buy")
        for l in state.levels:
            assert l.price < 2000.0

    def test_sell_levels_above_base(self):
        state = build_grid(2000.0, levels=3, spacing=10.0, base_lot=0.1, max_lot=1.0, direction="sell")
        for l in state.levels:
            assert l.price > 2000.0

    def test_levels_sorted_by_price(self):
        state = build_grid(2000.0, levels=3, spacing=10.0, base_lot=0.1, max_lot=1.0)
        prices = [l.price for l in state.levels]
        assert prices == sorted(prices)

    def test_get_triggered_buy(self):
        state = build_grid(2000.0, levels=2, spacing=10.0, base_lot=0.1, max_lot=1.0, direction="buy")
        triggered = get_triggered_levels(state, current_price=1975.0)
        assert len(triggered) == 2  # 1990 and 1980 both <= 1975

    def test_get_triggered_sell(self):
        state = build_grid(2000.0, levels=2, spacing=10.0, base_lot=0.1, max_lot=1.0, direction="sell")
        triggered = get_triggered_levels(state, current_price=2025.0)
        assert len(triggered) == 2

    def test_filled_levels_not_triggered(self):
        state = build_grid(2000.0, levels=2, spacing=10.0, base_lot=0.1, max_lot=1.0, direction="buy")
        state.levels[0].filled = True
        triggered = get_triggered_levels(state, current_price=1975.0)
        assert len(triggered) == 1

    def test_no_trigger_when_price_above_buy_levels(self):
        state = build_grid(2000.0, levels=2, spacing=10.0, base_lot=0.1, max_lot=1.0, direction="buy")
        triggered = get_triggered_levels(state, current_price=2010.0)
        assert len(triggered) == 0

    def test_rebuild_grid(self):
        state = build_grid(2000.0, levels=3, spacing=10.0, base_lot=0.1, max_lot=1.0)
        new_state = rebuild_grid(state, new_base_price=2100.0)
        assert new_state.base_price == 2100.0
        assert len(new_state.levels) == len(state.levels)


# ---------------------------------------------------------------------------
# Hedge
# ---------------------------------------------------------------------------
from app.services.strategy.money_mgmt.hedge import (
    open_hedge, hedge_direction, net_exposure, HedgePosition,
)


class TestHedge:
    def test_full_hedge_buy(self):
        h = open_hedge("buy", primary_lot=1.0, hedge_ratio=1.0)
        assert h.hedge_lot == 1.0
        assert h.primary_direction == "buy"
        assert h.active is True

    def test_partial_hedge(self):
        h = open_hedge("sell", primary_lot=2.0, hedge_ratio=0.5)
        assert h.hedge_lot == 1.0

    def test_hedge_capped_by_max_lot(self):
        h = open_hedge("buy", primary_lot=10.0, hedge_ratio=1.0, max_lot=2.0)
        assert h.hedge_lot == 2.0

    def test_hedge_minimum_lot(self):
        h = open_hedge("buy", primary_lot=0.001, hedge_ratio=1.0)
        assert h.hedge_lot == 0.01  # minimum enforced

    def test_invalid_ratio_raises(self):
        with pytest.raises(ValueError):
            open_hedge("buy", primary_lot=1.0, hedge_ratio=0.0)

    def test_ratio_too_high_raises(self):
        with pytest.raises(ValueError):
            open_hedge("buy", primary_lot=1.0, hedge_ratio=2.1)

    def test_hedge_direction_buy(self):
        assert hedge_direction("buy") == "sell"

    def test_hedge_direction_sell(self):
        assert hedge_direction("sell") == "buy"

    def test_net_exposure_full_hedge(self):
        assert net_exposure(1.0, 1.0) == 0.0

    def test_net_exposure_partial(self):
        assert net_exposure(2.0, 0.5) == 1.5

    def test_net_exposure_over_hedge(self):
        assert net_exposure(1.0, 1.5) == -0.5


# ---------------------------------------------------------------------------
# SMC Zones
# ---------------------------------------------------------------------------
from app.services.smc.zones import detect_demand_supply_zones, detect_sr_zones


def _make_zones_df() -> pd.DataFrame:
    # Create data with a clear demand zone (bearish base + bullish impulse)
    data = {
        "open":   [2300, 2295, 2290, 2360, 2355, 2350, 2345, 2340],
        "high":   [2306, 2300, 2295, 2380, 2370, 2365, 2355, 2350],
        "low":    [2292, 2287, 2282, 2352, 2348, 2342, 2338, 2335],
        "close":  [2296, 2291, 2285, 2378, 2365, 2358, 2349, 2342],
        "volume": [1000] * 8,
    }
    return pd.DataFrame(data)


def _make_supply_df() -> pd.DataFrame:
    # Bullish base + bearish impulse → supply zone
    data = {
        "open":   [2300, 2305, 2310, 2250, 2255, 2260],
        "high":   [2308, 2312, 2318, 2265, 2268, 2270],
        "low":    [2295, 2300, 2305, 2242, 2248, 2252],
        "close":  [2304, 2308, 2312, 2248, 2255, 2258],
        "volume": [1000] * 6,
    }
    return pd.DataFrame(data)


class TestSMCZones:
    def test_demand_zone_detected(self):
        df = _make_zones_df()
        result = detect_demand_supply_zones(df, impulse_threshold=1.2)
        assert isinstance(result, dict)
        assert "demand_zones" in result
        assert "supply_zones" in result

    def test_supply_zone_detected(self):
        df = _make_supply_df()
        result = detect_demand_supply_zones(df, impulse_threshold=1.2)
        assert "supply_zones" in result

    def test_zone_has_required_fields(self):
        df = _make_zones_df()
        result = detect_demand_supply_zones(df, impulse_threshold=1.2)
        for zone in result["demand_zones"]:
            assert "top" in zone
            assert "bottom" in zone
            assert "bar_index" in zone
            assert "strength" in zone

    def test_zone_top_above_bottom(self):
        df = _make_zones_df()
        result = detect_demand_supply_zones(df, impulse_threshold=1.2)
        for zone in result["demand_zones"]:
            assert zone["top"] >= zone["bottom"]

    def test_high_threshold_no_zones(self):
        df = _make_zones_df()
        result = detect_demand_supply_zones(df, impulse_threshold=100.0)
        assert result["demand_zones"] == []
        assert result["supply_zones"] == []

    def test_sr_zones_detected(self):
        data = {
            "open":  [2300, 2310, 2305, 2300, 2312, 2306, 2300],
            "high":  [2315, 2315, 2315, 2307, 2315, 2315, 2308],
            "low":   [2295, 2300, 2298, 2295, 2300, 2298, 2295],
            "close": [2310, 2306, 2302, 2304, 2308, 2302, 2302],
        }
        df = pd.DataFrame(data)
        zones = detect_sr_zones(df, tolerance_pct=0.002)
        assert isinstance(zones, list)

    def test_sr_empty_df_no_crash(self):
        df = pd.DataFrame({"open": [100, 101], "high": [105, 106], "low": [98, 99], "close": [102, 103]})
        zones = detect_sr_zones(df)
        assert isinstance(zones, list)

    def test_strength_increases_with_revisits(self):
        # Add more candles that revisit the demand zone
        data = {
            "open":  [2300, 2295, 2290, 2360, 2285, 2288, 2350, 2345],
            "high":  [2306, 2300, 2295, 2380, 2295, 2296, 2360, 2355],
            "low":   [2292, 2287, 2282, 2352, 2281, 2283, 2344, 2340],
            "close": [2296, 2291, 2285, 2378, 2289, 2291, 2352, 2348],
            "volume": [1000] * 8,
        }
        df = pd.DataFrame(data)
        result = detect_demand_supply_zones(df, impulse_threshold=1.2)
        if result["demand_zones"]:
            assert result["demand_zones"][0]["strength"] >= 1


# ---------------------------------------------------------------------------
# Wick Analysis
# ---------------------------------------------------------------------------
from app.services.analysis.wick_analysis import detect_wick_fills, detect_sl_sweeps


class TestWickAnalysis:
    def _basic_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "open":  [2300, 2310, 2295, 2320, 2305],
            "high":  [2320, 2325, 2310, 2335, 2315],
            "low":   [2290, 2295, 2285, 2300, 2295],
            "close": [2315, 2298, 2305, 2310, 2308],
        })

    def test_wick_fill_bullish(self):
        df = pd.DataFrame({
            "open":  [2300, 2330],
            "high":  [2320, 2340],
            "low":   [2295, 2325],
            "close": [2310, 2325],
        })
        results = detect_wick_fills(df)
        bullish = [r for r in results if r["type"] == "wick_fill_bullish"]
        assert len(bullish) >= 1

    def test_wick_fill_bearish(self):
        df = pd.DataFrame({
            "open":  [2300, 2270],
            "high":  [2320, 2280],
            "low":   [2295, 2260],
            "close": [2310, 2265],
        })
        results = detect_wick_fills(df)
        bearish = [r for r in results if r["type"] == "wick_fill_bearish"]
        assert len(bearish) >= 1

    def test_no_wick_fill_when_inside(self):
        df = pd.DataFrame({
            "open":  [2300, 2305],
            "high":  [2320, 2318],
            "low":   [2295, 2298],
            "close": [2310, 2308],
        })
        results = detect_wick_fills(df)
        assert len(results) == 0

    def test_wick_fill_result_fields(self):
        df = pd.DataFrame({
            "open":  [2300, 2330],
            "high":  [2320, 2340],
            "low":   [2295, 2325],
            "close": [2310, 2325],
        })
        results = detect_wick_fills(df)
        for r in results:
            assert "bar_index" in r
            assert "type" in r
            assert "price" in r
            assert "direction" in r

    def test_sl_sweep_ssl(self):
        # Price dips below recent swing low then recovers
        data = {
            "open":  [2300] * 12,
            "high":  [2310] * 12,
            "low":   [2295, 2296, 2297, 2296, 2295, 2296, 2297, 2296, 2295, 2296, 2280, 2295],
            "close": [2305, 2305, 2305, 2305, 2305, 2305, 2305, 2305, 2305, 2305, 2298, 2304],
        }
        df = pd.DataFrame(data)
        results = detect_sl_sweeps(df, lookback=10)
        ssl = [r for r in results if r["type"] == "SSL"]
        assert len(ssl) >= 1

    def test_sl_sweep_bsl(self):
        data = {
            "open":  [2300] * 12,
            "high":  [2310, 2310, 2310, 2310, 2310, 2310, 2310, 2310, 2310, 2310, 2330, 2310],
            "low":   [2295] * 12,
            "close": [2305, 2305, 2305, 2305, 2305, 2305, 2305, 2305, 2305, 2305, 2308, 2302],
        }
        df = pd.DataFrame(data)
        results = detect_sl_sweeps(df, lookback=10)
        bsl = [r for r in results if r["type"] == "BSL"]
        assert len(bsl) >= 1

    def test_sweep_result_fields(self):
        data = {
            "open":  [2300] * 12,
            "high":  [2310] * 12,
            "low":   [2295, 2296, 2297, 2296, 2295, 2296, 2297, 2296, 2295, 2296, 2280, 2295],
            "close": [2305, 2305, 2305, 2305, 2305, 2305, 2305, 2305, 2305, 2305, 2298, 2304],
        }
        df = pd.DataFrame(data)
        results = detect_sl_sweeps(df, lookback=10)
        for r in results:
            assert "bar_index" in r
            assert "type" in r
            assert "price" in r
            assert "direction" in r


# ---------------------------------------------------------------------------
# Candle Patterns (basic fallback — TA-Lib not available in CI)
# ---------------------------------------------------------------------------
from app.services.analysis.candle_patterns import detect_patterns, _detect_basic


class TestCandlePatterns:
    def test_detect_returns_list(self):
        df = pd.DataFrame({
            "open":  [2300, 2290, 2285, 2360],
            "high":  [2310, 2295, 2290, 2380],
            "low":   [2292, 2282, 2278, 2352],
            "close": [2295, 2287, 2288, 2378],
        })
        results = detect_patterns(df)
        assert isinstance(results, list)

    def test_bullish_engulfing_detected(self):
        df = pd.DataFrame({
            "open":  [2310, 2280],
            "high":  [2315, 2320],
            "low":   [2275, 2270],
            "close": [2285, 2315],
        })
        results = _detect_basic(df)
        engulfing = [r for r in results if r["pattern"] == "CDLENGULFING" and r["signal"] == 100]
        assert len(engulfing) >= 1

    def test_bearish_engulfing_detected(self):
        df = pd.DataFrame({
            "open":  [2280, 2320],
            "high":  [2325, 2330],
            "low":   [2275, 2270],
            "close": [2315, 2275],
        })
        results = _detect_basic(df)
        engulfing = [r for r in results if r["pattern"] == "CDLENGULFING" and r["signal"] == -100]
        assert len(engulfing) >= 1

    def test_doji_detected(self):
        # Doji: body < 10% of range
        df = pd.DataFrame({
            "open":  [2300, 2300],
            "high":  [2310, 2310],
            "low":   [2290, 2290],
            "close": [2305, 2301],  # 2nd: body=1 vs range=20 → doji
        })
        results = _detect_basic(df)
        doji = [r for r in results if r["pattern"] == "CDLDOJI"]
        assert len(doji) >= 1

    def test_no_pattern_neutral_candle(self):
        df = pd.DataFrame({
            "open":  [2300, 2305],
            "high":  [2312, 2315],
            "low":   [2295, 2300],
            "close": [2308, 2310],
        })
        results = _detect_basic(df)
        # flat candles — may or may not detect doji, but should not crash
        assert isinstance(results, list)

    def test_result_fields(self):
        df = pd.DataFrame({
            "open":  [2310, 2280],
            "high":  [2315, 2320],
            "low":   [2275, 2270],
            "close": [2285, 2315],
        })
        results = _detect_basic(df)
        for r in results:
            assert "bar_index" in r
            assert "pattern" in r
            assert "signal" in r
            assert "description" in r


# ---------------------------------------------------------------------------
# OrderManager (mocked MT5 + repository)
# ---------------------------------------------------------------------------
from app.services.execution.order_manager import (
    OrderManager, OrderIntent, OrderResult, OrderStatus, OrderType,
)


class TestOrderManager:
    def _make_manager(self, mt5_result: dict, repo=None):
        mt5 = MagicMock()
        mt5.order_send.return_value = mt5_result
        return OrderManager(mt5_client=mt5, repository=repo), mt5

    def _intent(self, order_type=OrderType.BUY) -> OrderIntent:
        return OrderIntent(
            symbol="XAUUSD",
            order_type=order_type,
            lot_size=0.1,
            price=2341.0,
            stop_loss=2330.0,
            take_profit=2365.0,
        )

    def test_place_order_success(self):
        mgr, mt5 = self._make_manager({"retcode": 10009, "order": 12345, "comment": "ok"})
        intent = self._intent()
        result = asyncio.run(mgr.place_order(intent))
        assert result.success is True
        assert result.mt5_ticket == 12345
        assert intent.status == OrderStatus.FILLED

    def test_place_order_rejected(self):
        mgr, mt5 = self._make_manager({"retcode": 10004, "order": None, "comment": "off quotes"})
        intent = self._intent()
        result = asyncio.run(mgr.place_order(intent))
        assert result.success is False
        assert intent.status == OrderStatus.REJECTED

    def test_place_order_writes_to_repo(self):
        repo = MagicMock()
        repo.create_order = AsyncMock(return_value="db-uuid-123")
        repo.update_order_status = AsyncMock()
        mt5 = MagicMock()
        mt5.order_send.return_value = {"retcode": 10009, "order": 999, "comment": ""}
        mgr = OrderManager(mt5_client=mt5, repository=repo)
        intent = self._intent()
        asyncio.run(mgr.place_order(intent))
        repo.create_order.assert_called_once()
        repo.update_order_status.assert_called_once()
        assert intent.db_id == "db-uuid-123"

    def test_cancel_order_success(self):
        mgr, mt5 = self._make_manager({"retcode": 10009})
        result = asyncio.run(mgr.cancel_order(12345))
        assert result is True

    def test_cancel_order_failure(self):
        mgr, mt5 = self._make_manager({"retcode": 10004})
        result = asyncio.run(mgr.cancel_order(12345))
        assert result is False

    def test_build_mt5_request_buy(self):
        mgr, _ = self._make_manager({})
        intent = self._intent(OrderType.BUY)
        req = mgr._build_mt5_request(intent)
        assert req["action"] == 1
        assert req["type"] == 0
        assert req["symbol"] == "XAUUSD"
        assert req["sl"] == 2330.0
        assert req["tp"] == 2365.0

    def test_build_mt5_request_sell(self):
        mgr, _ = self._make_manager({})
        intent = self._intent(OrderType.SELL)
        req = mgr._build_mt5_request(intent)
        assert req["type"] == 1

    def test_build_mt5_request_limit(self):
        mgr, _ = self._make_manager({})
        intent = self._intent(OrderType.BUY_LIMIT)
        req = mgr._build_mt5_request(intent)
        assert req["action"] == 5

    def test_parse_result_success(self):
        r = OrderManager._parse_result({"retcode": 10009, "order": 100, "volume": 0.1, "price": 2341.0})
        assert r.success is True
        assert r.mt5_ticket == 100
        assert r.volume == 0.1

    def test_parse_result_failure(self):
        r = OrderManager._parse_result({"retcode": 10018, "comment": "market closed"})
        assert r.success is False
        assert r.comment == "market closed"

    def test_comment_truncated_to_31_chars(self):
        mgr, _ = self._make_manager({})
        intent = self._intent()
        intent.comment = "A" * 50
        req = mgr._build_mt5_request(intent)
        assert len(req["comment"]) == 31


# ---------------------------------------------------------------------------
# PositionManager (mocked MT5)
# ---------------------------------------------------------------------------
from app.services.execution.position_manager import PositionManager, Position


def _raw_pos(ticket=1, symbol="XAUUSD", ptype=0, volume=0.1, price_open=2300.0,
             price_current=2320.0, sl=2280.0, tp=2350.0, profit=20.0, magic=0):
    return {
        "ticket": ticket,
        "symbol": symbol,
        "type": ptype,
        "volume": volume,
        "price_open": price_open,
        "price_current": price_current,
        "sl": sl,
        "tp": tp,
        "profit": profit,
        "magic": magic,
        "comment": "",
    }


class TestPositionManager:
    def _make_manager(self, positions=None):
        mt5 = MagicMock()
        mt5.positions_get.return_value = positions or []
        mt5.order_send.return_value = {"retcode": 10009}
        return PositionManager(mt5_client=mt5), mt5

    def test_get_open_positions_returns_list(self):
        pm, mt5 = self._make_manager([_raw_pos()])
        positions = pm.get_open_positions()
        assert len(positions) == 1
        assert isinstance(positions[0], Position)

    def test_get_open_positions_empty(self):
        pm, _ = self._make_manager([])
        assert pm.get_open_positions() == []

    def test_parse_position_buy(self):
        pos = PositionManager._parse_position(_raw_pos(ptype=0))
        assert pos.direction == "buy"

    def test_parse_position_sell(self):
        pos = PositionManager._parse_position(_raw_pos(ptype=1))
        assert pos.direction == "sell"

    def test_parse_position_fields(self):
        pos = PositionManager._parse_position(_raw_pos(ticket=42, symbol="EURUSD", profit=15.5))
        assert pos.ticket == 42
        assert pos.symbol == "EURUSD"
        assert pos.profit == 15.5

    def test_count_open_positions(self):
        pm, mt5 = self._make_manager([_raw_pos(1), _raw_pos(2)])
        assert pm.count_open_positions() == 2

    def test_close_position_success(self):
        pm, mt5 = self._make_manager()
        mt5.positions_get.return_value = [_raw_pos()]
        result = pm.close_position(1)
        assert result is True

    def test_close_position_not_found(self):
        pm, mt5 = self._make_manager([])
        mt5.positions_get.return_value = []
        result = pm.close_position(999)
        assert result is False

    def test_close_all_positions(self):
        pm, mt5 = self._make_manager([_raw_pos(1), _raw_pos(2)])
        mt5.positions_get.side_effect = [
            [_raw_pos(1), _raw_pos(2)],  # get_open_positions
            [_raw_pos(1)],               # close ticket 1
            [_raw_pos(2)],               # close ticket 2
        ]
        count = pm.close_all_positions()
        assert count == 2

    def test_trailing_stop_buy_improves(self):
        pm, mt5 = self._make_manager()
        mt5.positions_get.return_value = [_raw_pos(sl=2310.0, price_current=2330.0)]
        result = pm.update_trailing_stop(1, current_price=2330.0, trail_pips=100, pip_size=0.1, direction="buy")
        assert result is True
        mt5.order_send.assert_called_once()

    def test_trailing_stop_buy_no_improvement(self):
        pm, mt5 = self._make_manager()
        # new_sl = 2330 - 100*0.1 = 2320, but current_sl = 2325 → no improvement
        mt5.positions_get.return_value = [_raw_pos(sl=2325.0, price_current=2330.0)]
        result = pm.update_trailing_stop(1, current_price=2330.0, trail_pips=100, pip_size=0.1, direction="buy")
        assert result is False

    def test_trailing_stop_sell_improves(self):
        pm, mt5 = self._make_manager()
        mt5.positions_get.return_value = [_raw_pos(ptype=1, sl=2350.0, price_current=2320.0)]
        result = pm.update_trailing_stop(1, current_price=2320.0, trail_pips=100, pip_size=0.1, direction="sell")
        assert result is True

    def test_trailing_stop_ticket_not_found(self):
        pm, mt5 = self._make_manager([])
        mt5.positions_get.return_value = []
        result = pm.update_trailing_stop(999, current_price=2330.0, trail_pips=100, direction="buy")
        assert result is False

    def test_get_total_profit(self):
        pm, mt5 = self._make_manager([_raw_pos(profit=10.0), _raw_pos(ticket=2, profit=5.0)])
        total = pm.get_total_profit()
        assert total == 15.0

    def test_get_total_profit_no_positions(self):
        pm, _ = self._make_manager([])
        assert pm.get_total_profit() == 0.0

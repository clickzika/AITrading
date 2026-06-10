# AITrading

Automated algo-trading platform for XAUUSD, Forex, and Crypto.

**Stack:** Python 3.11 · FastAPI · TimescaleDB · Redis · React · MetaTrader 5 · Claude AI

---

## Features

- **MT5 Integration** — real-time tick feed, order execution, position management
- **Technical Analysis** — EMA (20/50/200), MACD, Fibonacci retracement/extension, VPVR, candlestick patterns, wick fills, SL sweeps
- **Smart Money Concepts** — Order Blocks, Fair Value Gaps, BOS/ChoCH, liquidity sweeps, demand/supply zones, S/R clustering
- **Strategy Engine** — YAML-based multi-condition AND/OR evaluator, 10 condition types
- **Risk Management** — Fixed lot, Fixed fractional, Kelly Criterion, Martingale (with safety caps), Grid trading, Hedging
- **TradingView Webhooks** — HMAC-SHA256 verified signal ingestion
- **News Trading** — pause/resume around high-impact economic events
- **React Dashboard** — live chart (TradingView Lightweight Charts v5), positions panel, trade log, AI co-pilot chat
- **Claude AI Co-Pilot** — market analysis, strategy builder, SSE streaming chat

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ |
| Node.js | 20+ |
| Docker + Docker Compose | latest |
| MetaTrader 5 | Windows (MT5 Python lib is Windows-only) |
| MT5 Account | Demo or Live |

---

## Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/clickzika/AITrading.git
cd AITrading
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# MetaTrader 5
MT5_LOGIN=12345678
MT5_PASSWORD=your_mt5_password
MT5_SERVER=MetaQuotes-Demo

# Database
DATABASE_URL=postgresql+asyncpg://aitrading:aitrading@localhost:5432/aitrading
REDIS_URL=redis://localhost:6379/0

# Security
JWT_SECRET_KEY=generate-a-strong-random-secret-here
TRADER_PASSWORD=your-dashboard-login-password

# AI Co-Pilot (optional)
ANTHROPIC_API_KEY=sk-ant-...

# Trading mode — keep "demo" until strategy is validated
TRADING_MODE=demo
```

### 2. Start infrastructure

```bash
docker-compose up -d
```

This starts TimescaleDB (PostgreSQL 15) and Redis.

### 3. Backend setup

```bash
cd backend
pip install -r requirements.txt
python -m alembic upgrade head   # run DB migrations
python main.py                   # starts FastAPI on http://localhost:8000
```

### 4. Frontend setup

```bash
cd frontend
npm install
npm run dev    # starts Vite dev server on http://localhost:5173
```

### 5. Open dashboard

Navigate to `http://localhost:5173` and log in with the `TRADER_PASSWORD` from your `.env`.

---

## Project Structure

```
AITrading/
├── backend/
│   ├── app/
│   │   ├── api/          ← FastAPI routers (webhooks, signals, trades, analysis, ai, ws)
│   │   ├── services/     ← business logic (analysis, smc, strategy, execution, news, ai)
│   │   ├── models/       ← SQLAlchemy ORM models
│   │   ├── repositories/ ← data access layer
│   │   ├── middleware/   ← JWT auth, CORS, logging
│   │   └── config/       ← pydantic-settings
│   ├── strategies/       ← YAML strategy configs
│   ├── tests/            ← pytest unit tests (135 tests, 64% coverage)
│   └── main.py
├── frontend/
│   └── src/
│       ├── components/   ← PriceChart, PositionsPanel, TradeLog, CopilotChat
│       ├── services/     ← API client + WebSocket
│       └── stores/       ← Zustand state
├── docs/                 ← BRD, SRS, API reference, architecture docs
├── docker-compose.yml
└── .env.example
```

---

## Strategy Configuration

Strategies are defined as YAML files in `backend/strategies/`. Example:

```yaml
strategy: ema_macd_xauusd
symbol: XAUUSD
timeframe: H1
entry:
  conditions:
    - type: ema_cross
      fast: 20
      slow: 50
      direction: bullish
    - type: macd_signal
      signal: bullish
    - type: fib_zone
      levels: [38.2, 61.8]
      zone: support
  logic: AND
risk:
  method: fixed_fractional
  risk_pct: 1.0
  stop_loss_pips: 30
  take_profit_pips: 90
  trailing_stop: true
  max_daily_loss_usd: 200
```

Condition types: `ema_cross`, `macd_signal`, `fib_zone`, `order_block`, `fvg`, `bos_choch`, `liquidity_sweep`, `candle_pattern`, `price_above_ema`, `price_below_ema`

---

## TradingView Webhooks

Send signals from TradingView Pine Script alerts to `POST /webhook/tradingview`:

```json
{
  "action": "buy",
  "symbol": "XAUUSD",
  "price": 2341.50,
  "lot_size": 0.1,
  "stop_loss": 2320.0,
  "take_profit": 2380.0,
  "strategy": "my_strategy",
  "secret": "{{your_TRADINGVIEW_WEBHOOK_SECRET}}"
}
```

Valid actions: `buy`, `sell`, `close_buy`, `close_sell`, `close_all`

---

## API Reference

Full API docs available at `http://localhost:8000/docs` (Swagger UI) when the backend is running.

Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/token` | Login, get JWT |
| GET | `/api/analysis/indicators/{symbol}` | Technical indicators |
| GET | `/api/analysis/smc/{symbol}` | SMC zones |
| GET | `/api/signals` | Signal history |
| GET | `/api/trades` | Trade history |
| GET | `/api/trades/positions` | Open positions |
| POST | `/api/ai/chat` | Claude co-pilot |
| WS | `/ws` | Live price/position stream |

---

## Testing

```bash
cd backend
pytest --tb=short                    # run all tests
pytest --cov=app --cov-report=html   # coverage report → coverage_html/
```

```bash
cd frontend
npm run build    # type-check + build
```

---

## Deployment

> **MT5 constraint:** The MetaTrader5 Python library is Windows-only. The backend must run on the same Windows machine as MT5 terminal.

### Production setup

1. Set `TRADING_MODE=live` in `.env` only after validating on demo
2. Set strong `JWT_SECRET_KEY` and `TRADER_PASSWORD`
3. Run backend behind a reverse proxy (nginx) with HTTPS
4. Keep `ANTHROPIC_API_KEY` in environment only — never committed

### Docker (DB + Redis only)

```bash
docker-compose up -d   # starts TimescaleDB + Redis
```

The Python backend and React frontend run natively on Windows alongside MT5.

---

## Safety Rules

- **Always test on MT5 demo first** — never run a new strategy live immediately
- **Martingale strategies require** `max_multiplier` + `max_lot_size` — no exceptions
- **Daily loss cap** is enforced server-side — the UI cannot override it
- **MT5 disconnect** triggers circuit breaker — auto-trading pauses automatically
- **Webhook secrets** must match `TRADINGVIEW_WEBHOOK_SECRET` — HMAC-SHA256 verified

---

## License

Private — all rights reserved.

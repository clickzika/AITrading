# AITrading — Claude Code Spec

## Project Overview
| Field | Value |
|-------|-------|
| Name | AITrading |
| Description | Automated algo-trading platform for XAUUSD, Forex, and Crypto with full SMC + classical TA toolkit, MT5 auto-execution, TradingView webhook signals, and Claude AI co-pilot |
| Stakeholders | Solo trader (clickzika) |
| Project Type | Web App (React dashboard) + Background Services (Python engine) + REST/WebSocket API (FastAPI) |
| Frontend / UI | React + TradingView Lightweight Charts |
| Backend | Python 3.11+ / FastAPI + uvicorn |
| Database | TimescaleDB (PostgreSQL extension) |
| ORM | SQLAlchemy 2.0 (async) |
| Auth | JWT (single-user, API key for webhooks) |
| Authorization | Single-user — no RBAC needed |
| Deploy | Windows local (MT5 constraint) + Docker for DB/Redis |
| CI/CD | GitHub Actions |
| Extra | MetaTrader5 Python lib · Redis pub/sub · pandas-ta · Anthropic SDK · YAML strategy configs |

## Folder Structure

```
AITrading/
├── backend/                     ← Python FastAPI application
│   ├── app/
│   │   ├── api/                 ← FastAPI route handlers
│   │   │   ├── webhooks/        ← TradingView webhook endpoints
│   │   │   ├── signals/         ← signal CRUD + WebSocket
│   │   │   ├── trades/          ← trade log + position endpoints
│   │   │   ├── analysis/        ← indicator + chart data endpoints
│   │   │   └── ai/              ← Claude co-pilot chat endpoint
│   │   ├── services/            ← business logic
│   │   │   ├── analysis/        ← MACD, EMA, Fibonacci, candle patterns
│   │   │   │   ├── indicators.py
│   │   │   │   ├── fibonacci.py
│   │   │   │   ├── candle_patterns.py
│   │   │   │   └── volume_profile.py
│   │   │   ├── smc/             ← Smart Money Concepts
│   │   │   │   ├── order_blocks.py
│   │   │   │   ├── fvg.py       ← Fair Value Gaps
│   │   │   │   ├── bos_choch.py ← Break of Structure / ChoCH
│   │   │   │   └── liquidity.py ← Sweep detection
│   │   │   ├── strategy/        ← strategy evaluation engine
│   │   │   │   ├── engine.py    ← YAML config loader + evaluator
│   │   │   │   ├── risk.py      ← risk manager (lot sizing, SL/TP, limits)
│   │   │   │   └── money_mgmt/  ← Kelly, fixed fractional, martingale, grid, hedge
│   │   │   ├── execution/       ← MT5 order management
│   │   │   │   ├── mt5_client.py
│   │   │   │   ├── order_manager.py
│   │   │   │   └── position_manager.py
│   │   │   ├── market_data/     ← data ingestion
│   │   │   │   ├── mt5_feed.py
│   │   │   │   └── ohlcv_store.py
│   │   │   ├── news/            ← news trading service
│   │   │   │   └── calendar.py
│   │   │   └── ai/              ← Claude co-pilot service
│   │   │       └── copilot.py
│   │   ├── models/              ← SQLAlchemy ORM models
│   │   ├── repositories/        ← data access layer
│   │   ├── middleware/          ← JWT auth, CORS, logging
│   │   ├── config/              ← settings (pydantic-settings)
│   │   └── utils/
│   ├── strategies/              ← YAML strategy config files
│   │   ├── ema_macd_xauusd.yml
│   │   ├── smc_h1_eurusd.yml
│   │   └── grid_btcusd.yml
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── alembic/                 ← DB migrations
│   ├── requirements.txt
│   └── main.py
│
├── frontend/                    ← React dashboard
│   ├── src/
│   │   ├── components/
│   │   │   ├── charts/          ← TradingView LW Charts
│   │   │   ├── dashboard/       ← live positions, P&L
│   │   │   ├── trades/          ← trade log table
│   │   │   ├── strategy/        ← strategy config editor
│   │   │   └── ai/              ← Claude co-pilot chat UI
│   │   ├── pages/
│   │   ├── services/            ← API client + WebSocket
│   │   ├── stores/              ← Zustand state
│   │   └── utils/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
│
├── database/
│   └── migrations/              ← managed by Alembic
│
├── docs/
│   ├── index.html               ← Document Portal
│   ├── brd.html
│   ├── srs.html
│   ├── database-design.html
│   ├── api-reference.html
│   ├── security-design.html
│   ├── infrastructure-guide.html
│   ├── test-strategy.html
│   ├── project-plan.html
│   └── prototype/
│       ├── index.html
│       └── components.html
│
├── .github/
│   ├── workflows/
│   │   └── ci.yml
│   ├── pull_request_template.md
│   └── ISSUE_TEMPLATE/
│
├── memory/
│   └── progress.json
│
├── docker-compose.yml
├── CLAUDE.md                    ← this file
├── devstarter-config.yml
├── .env.example
├── .gitignore
└── README.md
```

## Architecture

**Pattern:** Event-Driven Hybrid

```
Signal Sources (TradingView webhooks / MT5 feed)
  ↓
FastAPI Gateway (Python) — /webhook/tradingview | /api/* | /ws
  ↓ Redis pub/sub
Redis (message bus + cache)
  ↙                    ↘
Analysis Engine         Strategy Engine
(pandas-ta, SMC)        (YAML rule evaluator + risk manager)
                          ↓
                    MT5 Execution Engine (MetaTrader5 Python lib)
                          ↓
                    TimescaleDB (OHLCV + trades + positions)
                          ↓
                    React Dashboard (live WebSocket updates)
                    + Claude AI Co-Pilot (Anthropic SDK)
```

**Key constraints:**
- MetaTrader5 Python lib = Windows-only — execution engine runs on same Windows machine as MT5
- Always test strategies on MT5 demo account before live trading
- TradingView free plan has 15-min delay — use MT5 feed as primary real-time data source
- Fibonacci levels recompute per candle close (not every tick)

## Security

### Basic Security (always applied)
- HTTPS enforced in production
- CORS: allow only `localhost` + configured origins
- Input validation on all webhook payloads (pydantic)
- Secrets via `.env` — never hardcoded
- DTOs only — never expose MT5 account credentials in responses
- Webhook signature verification (TRADINGVIEW_WEBHOOK_SECRET)

### OWASP Top 10
- A01 Broken Access Control: JWT required on all protected endpoints
- A02 Cryptographic Failures: JWT in env, bcrypt for any stored credentials, TLS 1.2+
- A03 Injection: SQLAlchemy parameterized queries, pydantic validation on all inputs
- A04 Insecure Design: risk manager hard-limits enforced in service layer, not just UI
- A05 Misconfiguration: CORS whitelist, no debug endpoints in production
- A07 Auth Failures: JWT 24h expiry, rate limiting on auth endpoints
- A09 Logging: structured logs, never log MT5 password or API keys

### Trading Safety
- Risk manager enforces: max daily loss cap, max open positions, lot size limits
- MT5 connection loss → auto-pause all auto-trading (circuit breaker)
- Martingale strategy: configurable max multiplier + safety cap mandatory
- All orders logged to DB before MT5 send — audit trail

## User Roles

| Role | Access |
|------|--------|
| Trader (admin) | Full access — all endpoints, all strategies, live trading |

Single-user system. No multi-user auth needed.

## Features

### Phase 1 — Core Engine
- [x] MT5 connection + price feed ingestion
- [ ] OHLCV storage to TimescaleDB (XAUUSD, EURUSD, BTCUSD)
- [ ] Technical analysis: MACD, EMA (20/50/200), Fibonacci retracements
- [ ] Fibonacci Time Zones + Fibonacci Cycles
- [ ] Volume Profile (VPVR)
- [ ] Candlestick pattern recognition
- [ ] SMC: Order Blocks, Fair Value Gaps, BOS/ChoCH, liquidity sweep detection
- [ ] Support & Resistance zones, Demand & Supply zones
- [ ] Wick fill analysis, Stop Loss sweep detection
- [ ] Manual order execution via Python CLI

### Phase 2 — Strategy + Auto-Trade
- [ ] YAML strategy config loader
- [ ] Strategy evaluation engine (multi-condition AND/OR logic)
- [ ] TradingView webhook receiver (/webhook/tradingview)
- [ ] MT5 auto-execution with SL/TP management
- [ ] Risk manager: fixed lot, fixed fractional, Kelly Criterion
- [ ] Martingale strategy (configurable multiplier + safety cap)
- [ ] Grid trading strategy (fixed/dynamic spacing)
- [ ] Hedging (simultaneous opposing positions)
- [ ] News trading (economic calendar integration, pause/trigger)
- [ ] HFT-style scalping mode (tick-level signal evaluation)
- [ ] Trailing stop management
- [ ] Daily loss cap + drawdown limit enforcement

### Phase 3 — Dashboard + AI
- [ ] FastAPI REST API + WebSocket (live price/position stream)
- [ ] React dashboard with TradingView Lightweight Charts
- [ ] Strategy overlay on chart (entry/exit signals, SMC zones)
- [ ] Live positions + real-time P&L
- [ ] Trade history log with filter/sort/export
- [ ] Strategy config editor (YAML editor in UI)
- [ ] Performance analytics (win rate, RR ratio, drawdown chart)
- [ ] Claude AI co-pilot chat (market analysis, strategy builder, trade explanations)
- [ ] Claude daily market report (cron-generated multi-timeframe analysis)

## Coding Standards

### Python
- Python 3.11+, strict typing with `from __future__ import annotations`
- `ruff` for linting/formatting (line length 100)
- `pydantic` v2 for all data validation
- `async/await` throughout — no blocking I/O on the main thread
- SQLAlchemy 2.0 async sessions
- All services injectable — no singletons with state

### TypeScript / React
- TypeScript strict mode
- Functional components only, no class components
- Zustand for state management
- React Query for server state
- Named exports only

### YAML Strategy Config
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

## Testing Strategy

### Unit Tests (pytest)
- Analysis engine: MACD, EMA, Fibonacci calculations
- SMC detection algorithms
- Strategy YAML loader + evaluator
- Risk manager calculations (lot sizing, Kelly, daily loss)
- MT5 client mock (simulate responses without real MT5)

### Integration Tests
- FastAPI endpoints (TestClient)
- TradingView webhook parsing
- TimescaleDB read/write
- Redis pub/sub message flow

### Manual Testing
- Always test strategy on MT5 demo before live
- Visual chart overlay verification in dashboard

## Code Quality
- ruff (Python linting + formatting)
- mypy (type checking)
- pytest (tests)
- pre-commit hooks: ruff, mypy before commit

## ⚠️ Gate Approval Rules

STOP at every gate. Show output. Wait for "approve" or "revise [notes]". Never continue without explicit approval.

### What agents MUST do at each gate
1. Complete all tasks for the current gate
2. Save all output files to disk
3. Commit to git
4. Update memory/progress.json
5. Show the GATE APPROVAL REQUIRED message
6. STOP and wait

### What agents MUST do when resuming any session
1. Read memory/progress.json — find current gate and last step
2. Read the actual docs file from disk (NOT chat history)
3. Announce what was read and from where
4. Continue from "Next action" in progress.json

## Progress Tracker

### Gate 0 — Setup ✅
- [x] devstarter-config.yml created
- [x] .gitignore + .env.example created
- [x] git init + branches: main, uat, develop
- [x] GitHub remote: github.com/clickzika/AITrading
- [x] Auto-resume cron configured

### Gate 1 — Discovery ⛔ requires approval
- [x] CLAUDE.md written
- [ ] docs/brd.html (BRD + User Stories + Acceptance Criteria)
- [ ] docs/srs.html (Software Requirements Specification)
- [ ] **GATE 1 APPROVAL** — waiting for user

### Gate 2 — Architecture ⛔ requires approval
- [ ] docs/database-design.html
- [ ] docs/api-reference.html
- [ ] docs/security-design.html
- [ ] docs/infrastructure-guide.html
- [ ] docs/test-strategy.html
- [ ] docs/prototype/index.html + components.html
- [ ] docs/project-plan.html
- [ ] **GATE 2 APPROVAL**

### Gate 3 — Foundation ⛔ requires approval
- [ ] Docker Compose (TimescaleDB + Redis)
- [ ] Python backend scaffold + /health endpoint
- [ ] React frontend scaffold
- [ ] GitHub Issues + milestones created
- [ ] **GATE 3 APPROVAL**

### Gate 4 — Feature Development (continuous)
- [ ] Phase 1: analysis engine + MT5 feed
- [ ] Phase 2: strategy engine + auto-execution
- [ ] Phase 3: dashboard + Claude AI co-pilot

### Gate 5 — Quality & Delivery ⛔ requires approval before deploy
- [ ] All tests passing, coverage report
- [ ] Security checklist verified
- [ ] CI/CD pipeline passing
- [ ] README + deployment guide

## Last Checkpoint
**Status:** IN PROGRESS
**Gate:** 1
**Last completed:** CLAUDE.md written
**Next action:** Write docs/brd.html, then docs/srs.html
**Files modified:** CLAUDE.md, devstarter-config.yml, .gitignore, .env.example

## Resume Instructions
1. Read memory/progress.json first
2. Read CLAUDE.md from disk (NOT chat history)
3. Announce: "📂 Resuming Gate [N] — read from CLAUDE.md"
4. Continue from "Next action" above
5. Do NOT skip gate approvals even when resuming

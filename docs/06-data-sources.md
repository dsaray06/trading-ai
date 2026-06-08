# 06 — Data Sources & Integrations

All external data and execution sit behind adapter interfaces in `backend/app/services/data_sources/` and `backend/app/services/execution/`. Agents and services depend on these interfaces, never on a vendor SDK directly. This keeps vendors swappable and makes testing easy (mock the interface).

## Principles

- **One adapter per provider**, each implementing a small internal interface (e.g. `PriceDataSource`, `FundamentalsSource`, `NewsSource`, `OptionsSource`).
- **Normalize** vendor responses into internal Pydantic models before returning.
- **Cache** aggressively (prices, fundamentals, filings) to respect free-tier rate limits — start with an in-process TTL cache; move to Redis/Postgres if needed.
- **Degrade gracefully:** if a source is down, the dependent agent should abstain rather than crash the whole run.
- **Keys from env only** (`app/core/config.py`). See `.env.example`.

## Market data providers

### Polygon (`polygon-api-client`)
Primary source for historical and intraday equity/ETF prices, aggregates, and options chains/contracts. Used by the Market and Options agents. Mind free-tier rate limits; cache aggregates.

### Finnhub (`finnhub-python`)
Company fundamentals, earnings, analyst recommendations/upgrades-downgrades, and company news. Used by the Fundamental and News & Sentiment agents.

### yfinance
Convenient fallback for prices, fundamentals, and basic options data when Polygon/Finnhub quotas are tight. Treat as best-effort (unofficial API); never the sole source for anything critical.

### SEC EDGAR (`sec-edgar-downloader` / EDGAR REST)
Primary-source filings (10-K, 10-Q, 8-K) for the Fundamental agent's deeper analysis and the Sentiment agent's catalyst detection. **Set a descriptive `User-Agent`** (`SEC_EDGAR_USER_AGENT`) — EDGAR requires it and rate-limits anonymous traffic.

### Source-to-agent mapping
| Agent | Primary sources |
|---|---|
| Market Analysis | Polygon (prices/aggregates), yfinance fallback |
| Fundamental | Finnhub fundamentals, SEC EDGAR filings, yfinance fallback |
| News & Sentiment | Finnhub news + analyst actions, SEC 8-K |
| Options Analysis | Polygon options chains/contracts |
| Holdings / Risk | Alpaca positions + Polygon prices |

## Execution: Alpaca paper trading (`alpaca-py`)

We integrate Alpaca's **paper-trading** API instead of building a custom fill engine. This gives realistic simulated execution, position tracking, and portfolio sync with little code, and demonstrates real brokerage-API integration.

**Hard rule:** only ever use the paper endpoint:
```
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```
Never configure or call the live trading endpoint. Add a guard in the execution service that refuses to start if the base URL is not the paper host.

**Responsibilities of the execution service (`services/execution/alpaca.py`):**
- Submit simulated orders derived from accepted recommendations.
- Sync positions, cash balance, and portfolio value back into Postgres.
- Record fills in `trades`; reconcile via `alpaca_order_id`.
- Be idempotent: accepting the same recommendation twice must not double-submit.

**Equities vs options:** equities/ETFs are straightforward via Alpaca. Options paper trading depends on Alpaca account options approval/level; if unavailable, fall back to recording the simulated options trade internally (mark-to-model) and flag it in the UI. Document whichever path you implement.

### Optional later: QuantConnect / IBKR / Schwab sandbox
The original concept listed several brokerage sandboxes. Alpaca is the chosen default for its free, easy paper API. Others (Interactive Brokers paper, Schwab developer sandbox, QuantConnect) are possible future integrations behind the same `ExecutionProvider` interface — not in scope for the MVP.

## Backtesting data

The backtesting engine reuses the price adapters for historical data. Critical: **no look-ahead bias** — when replaying date `t`, only feed agents data available at `t`. Benchmarks (SPY, QQQ, VTI, or a user-selected symbol) come from the same price sources.

## Getting API keys (free tiers)

- **Anthropic (Claude):** required for all agent reasoning.
- **Alpaca:** free paper-trading account → API key + secret.
- **Polygon:** free tier (rate-limited).
- **Finnhub:** free tier.
- **yfinance / SEC EDGAR:** no key (EDGAR needs a User-Agent).

Put them all in `.env` (copy from `.env.example`).

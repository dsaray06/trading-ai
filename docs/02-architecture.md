# 02 — System Architecture

## High-level flow

```
                         ┌──────────────────────────┐
                         │   React + TS Frontend     │
                         │ (Research/Portfolio/      │
                         │  Backtesting tabs)        │
                         └────────────┬─────────────┘
                                      │ HTTPS / JSON (JWT)
                                      ▼
                         ┌──────────────────────────┐
                         │     FastAPI Backend       │
                         │  auth · routers · schemas │
                         └────────────┬─────────────┘
                                      │
              ┌───────────────────────┼────────────────────────┐
              ▼                       ▼                         ▼
   ┌────────────────────┐  ┌────────────────────┐   ┌────────────────────┐
   │ LangGraph Agent    │  │  Data Source Layer │   │ Execution Service  │
   │ Orchestrator       │  │ Polygon/Finnhub/   │   │ (Alpaca paper API) │
   │                    │  │ yfinance/SEC EDGAR │   │                    │
   │  Market Analysis   │  └─────────┬──────────┘   └─────────┬──────────┘
   │  Fundamental       │            │                        │
   │  News & Sentiment  │◀───────────┘                        │
   │  Options Analysis  │                                     │
   │  Holdings Review   │            ┌────────────────────────┘
   │  Portfolio Risk    │            │
   │  Trade Decision    │            ▼
   └─────────┬──────────┘   ┌────────────────────┐
             │              │  Backtesting Engine │
             ▼              │  (pandas / NumPy)   │
   ┌────────────────────┐   └─────────┬──────────┘
   │     PostgreSQL     │◀────────────┘
   │ users·portfolios·  │
   │ positions·trades·  │
   │ recommendations·   │
   │ agent_votes·       │
   │ backtests          │
   └────────────────────┘
```

(The original concept diagram listed a custom paper-trading engine; we substitute the Alpaca execution service. See `docs/00-overview.md` design decisions.)

## Components

### Frontend (React + TypeScript)
A Vite SPA with three tabs. Talks to the backend over REST/JSON, sends the JWT in the `Authorization` header. Charts with Recharts. Tailwind for styling. State kept simple (React Query-style fetching or hand-rolled hooks in `src/hooks/`); no heavy global store needed early.

### Backend (FastAPI)
Owns auth, request validation (Pydantic schemas), persistence, and orchestrates the agent graph and the execution/backtesting services. Routers live in `app/api/routes/`; business logic in `app/services/`; agents in `app/agents/`. Async handlers throughout.

### Agent orchestrator (LangGraph)
A directed graph that fans out a security to the analysis agents, then funnels their structured outputs into the Trade Decision agent. Each agent is a node with a typed input and a typed output (see `docs/03-agents.md`). The graph is the single place that defines execution order, parallelism, and how votes are aggregated. Agents call the Claude API for reasoning and the data-source layer for facts.

### Data source layer
Adapters that normalize Polygon, Finnhub, yfinance, and SEC EDGAR into internal models. Each source sits behind an interface so agents depend on `services.data_sources`, not on a vendor SDK. Includes caching and rate-limit handling. See `docs/06-data-sources.md`.

### Execution service (Alpaca)
Wraps `alpaca-py` against the **paper** endpoint only. Submits simulated orders derived from accepted recommendations, syncs positions and portfolio value back into Postgres, and records fills in `trades`.

### Backtesting engine
Replays a strategy over historical data with no look-ahead, simulates trades, and computes performance + risk metrics. Pure pandas/NumPy; deterministic given a seed. See `docs/03-agents.md` (Decision agent) and `docs/07-roadmap.md` (Phase 5).

### Database (PostgreSQL)
System of record for users, portfolios, positions, trades, recommendations, agent votes, and backtest results. SQLAlchemy ORM + Alembic migrations. Schema in `docs/04-data-model.md`.

## Request lifecycles

**Research a ticker**
1. `POST /research/{ticker}` (authenticated).
2. Backend invokes the LangGraph orchestrator.
3. Analysis agents fetch data (cached where possible) and each return scores + a vote.
4. Trade Decision agent aggregates via weighted voting → final recommendation + confidence + reasoning.
5. Recommendation + per-agent votes persisted; response returned to the Research tab.

**Accept a recommendation (paper trade)**
1. `POST /portfolio/{id}/trades` with a recommendation id.
2. Execution service submits a paper order to Alpaca.
3. On fill, positions/cash sync back; `trades` row written; Portfolio tab reflects it.

**Run a backtest**
1. `POST /backtests` with a strategy + horizon + benchmark.
2. Backtesting engine replays history, computes metrics, persists results.
3. Backtesting tab renders the equity curve and stats.

## Infrastructure & deployment

- **Local:** `docker-compose` runs Postgres + backend + frontend.
- **CI:** GitHub Actions runs ruff, pytest, and the frontend type-check on every PR.
- **Cloud (later phase):** backend container on **EC2**, managed Postgres on **RDS**, artifacts/exports on **S3**. Keep deploy concerns out of the MVP; see `docs/07-roadmap.md` Phase 6.

## Non-functional notes

- **Secrets**: env-only via `app/core/config.py`.
- **Idempotency**: accepting the same recommendation twice must not double-submit an order.
- **Observability**: structured logging from day one; tag logs with request id and (in backtests) run id.
- **Reproducibility**: backtests and scoring must be deterministic given identical inputs + seed.

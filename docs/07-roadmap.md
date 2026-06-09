# 07 — Build Roadmap (MVP-first)

The destination is the full vision in `docs/00-overview.md`. The path is incremental: each phase is **shippable and demoable on its own**, and each builds on the last. Do not start a phase before the previous one runs end-to-end.

---

## Phase 0 — Foundations
**Goal:** the skeleton runs.
- `docker compose up` brings up Postgres + backend + frontend.
- FastAPI `/health` returns ok; React app renders the empty 3-tab shell.
- `app/core/config.py` loads settings from `.env`; logging configured.
- Alembic initialized; one empty baseline migration.
- CI (ruff + pytest + frontend typecheck) green.

**Done when:** a fresh clone + `.env` + `docker compose up` works and CI passes.

---

## Phase 1 — One agent, end-to-end
**Goal:** prove the vertical slice with the **Market Analysis agent only**.
- Polygon (or yfinance) price adapter behind `PriceDataSource`.
- Market Analysis agent computes RSI/MACD/MA/Bollinger/volatility and emits a vote.
- A *trivial* Decision step (single-agent passthrough) returns a recommendation.
- `POST /research/{ticker}` persists and returns the recommendation.
- Research tab renders the recommendation + technical indicators.
- Unit tests for the indicator math (fixed-input fixtures).

**Done when:** you can search a ticker in the UI and see a real, explained technical recommendation.

---

## Phase 2 — Full agent roster + voting
**Goal:** the multi-agent system that defines the project.
- Add Fundamental, News & Sentiment agents (Finnhub + SEC EDGAR adapters).
- Implement the LangGraph orchestrator fanning out to agents in parallel.
- Implement `aggregate_votes` (weighted voting + confidence) as a pure, tested function (`docs/03-agents.md`).
- Trade Decision agent produces thesis + reasoning report via Claude.
- Research tab shows the full agent-vote breakdown + reasoning report.
- Persist `recommendations` + `agent_votes`.

**Done when:** a recommendation reflects ≥3 agents voting, with a confidence score and an explanation, matching the worked example in `docs/03-agents.md`.

---

## Phase 3 — Portfolio + paper execution
**Goal:** simulated trading via Alpaca.
- Auth (JWT + register/login); portfolios owned by users.
- Alpaca paper execution service (paper-endpoint guard, idempotent orders).
- Accept a recommendation → paper order → sync positions/cash.
- Holdings Review agent + Portfolio Risk agent (position sizing, stops, exposure).
- Portfolio tab: value, cash, positions, allocation, daily P/L, trade history, per-holding AI recommendation, risk metrics.

**Done when:** you can accept a recommendation, see it execute on paper, and watch the portfolio update — with a holdings review on each position.

---

## Phase 4 — Options
**Goal:** options analysis and (paper) options trades.
- Options Analysis agent: IV, Greeks, expected payoff, strike/expiration selection, liquidity.
- Polygon options-chain adapter.
- Buy Call / Buy Put recommendations end-to-end; render in Research tab.
- Paper options execution via Alpaca where available, else mark-to-model fallback (`docs/06-data-sources.md`).

**Done when:** the NVDA-style options recommendation in `docs/01-product-spec.md` can be produced and (paper) executed.

---

## Phase 5 — Backtesting
**Goal:** validate strategies historically.
- Backtesting engine (pandas/NumPy), strictly no look-ahead, deterministic with a seed.
- Metrics: total/annualized return, win rate, profit factor, Sharpe, Sortino, max drawdown, benchmark-adjusted return, average trade return.
- Benchmarks: SPY/QQQ/VTI/custom; horizons: 1/3/5/10Y.
- `POST /backtests`, results persisted; Backtesting tab renders equity curve + stats + strategy comparison.

**Done when:** you can backtest a strategy over multiple horizons and compare against a benchmark.

---

## Phase 6 — Cloud deploy + hardening
**Goal:** make it production-shaped.
- Containerized deploy on **Render** (Blueprint): Docker backend + managed Postgres + static frontend.
- GitHub Actions CI; Render auto-deploys on merge to main.
- OAuth 2.0 login; secrets via env/secret manager; rate-limit + retry on data sources; structured logging/metrics.
- A persistent disclaimer surface in the UI and API.

**Done when:** the app is reachable at a URL, deploys from CI, and is safe to demo publicly.

---

## Future enhancements (optional)
From the original concept — pursue only after the core is solid:
- **ML models:** directional movement, volatility forecasting, trade-success probability, risk forecasting (XGBoost, Random Forest, LSTM, transformer time-series). Adds the scikit-learn/ML story.
- **Portfolio optimization:** mean-variance, risk parity, Kelly-criterion sizing, volatility targeting.
- **Strategy marketplace:** users create, save, backtest, and compare custom strategies.
- **More execution providers:** IBKR paper, Schwab sandbox, QuantConnect behind the existing `ExecutionProvider` interface.

## Sequencing advice
- Keep each phase's PR set small and vertical.
- Write the agent-scoring and backtest math as pure functions with unit tests — they're the parts most likely to be quietly wrong.
- Update `docs/` in the same change whenever a contract changes.
- Tag a git release at the end of each phase so you always have a working demo to show.

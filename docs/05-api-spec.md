# 05 — API Specification

FastAPI, REST/JSON. All routes except auth and health require a valid JWT (`Authorization: Bearer <token>`). Request/response bodies are Pydantic models in `backend/app/schemas/`. Interactive docs are auto-generated at `/docs`.

This is the target surface. Build it incrementally per `docs/07-roadmap.md`; the Phase-1 minimum is health + auth + `POST /research/{ticker}`.

## Conventions

- Base path: `/` (no version prefix for MVP; add `/v1` later if needed).
- Errors: standard FastAPI `{ "detail": ... }`, correct HTTP status codes.
- Timestamps: ISO 8601 UTC.
- Money/quantities: numbers (serialized from `numeric`).
- Every recommendation payload includes a `disclaimer` field.

## Health

```
GET /health → 200 { "status": "ok" }
```

## Auth

```
POST /auth/register      { email, password } → 201 { user }
POST /auth/login         { email, password } → 200 { access_token, token_type }
GET  /auth/oauth/{provider}        → 302 redirect to provider
GET  /auth/oauth/{provider}/callback → 200 { access_token, token_type }
GET  /auth/me            → 200 { user }
```

## Research

```
POST /research/{ticker}
  body: { asset_type?: "stock"|"etf"|"option", horizon?: "short"|"medium"|"long",
          include_options?: bool }
  → 200 RecommendationResponse
```

`RecommendationResponse` (see `TradeDecision` in `docs/03-agents.md`):
```json
{
  "id": "uuid",
  "ticker": "NVDA",
  "asset_type": "option",
  "action": "Buy Call",
  "entry_target": 4.20,
  "exit_target": null,
  "stop_loss": -35,
  "take_profit": 60,
  "position_size": 2,
  "confidence": 74,
  "thesis": "…",
  "reasoning_report": "…",
  "agent_votes": [
    {"agent":"market","action":"Buy","score":78,"weight":0.20,"reasoning":"…"},
    {"agent":"fundamental","action":"Buy","score":84,"weight":0.25,"reasoning":"…"}
  ],
  "analysis": {
    "technical": { "...": "..." },
    "fundamental": { "...": "..." },
    "sentiment": { "...": "..." },
    "options": { "...": "..." }
  },
  "disclaimer": "Research / paper trading only. Not financial advice."
}
```

```
GET  /research/{ticker}/history → recent recommendations for a ticker
GET  /recommendations/{id}      → fetch a stored recommendation + votes
```

## Portfolio

```
GET  /portfolios                       → list user portfolios
POST /portfolios                       { name, starting_cash } → create
GET  /portfolios/{id}                  → portfolio value, cash, daily P/L, risk metrics
GET  /portfolios/{id}/positions        → open positions + per-position AI recommendation
GET  /portfolios/{id}/allocation       → allocation breakdown (by sector/asset)
GET  /portfolios/{id}/trades           → trade history
GET  /portfolios/{id}/benchmark        ?symbol=SPY → portfolio vs benchmark series
POST /portfolios/{id}/review           → run Holdings Review across all positions
```

### Accept a recommendation (paper trade)
```
POST /portfolios/{id}/trades
  body: { recommendation_id, quantity?, override_price? }
  → 201 { trade }       # submits an Alpaca PAPER order, syncs position
```
Must be idempotent on `recommendation_id` (don't double-submit).

```
POST /portfolios/{id}/sync   → pull positions/cash from Alpaca paper account
```

## Backtesting

```
GET  /backtests                 → list past runs
POST /backtests
  body: { strategy, params?, benchmark: "SPY"|"QQQ"|"VTI"|"custom",
          horizon: "1Y"|"3Y"|"5Y"|"10Y", start_date?, end_date? }
  → 202 { backtest_id }         # may run async for long horizons
GET  /backtests/{id}            → metrics + equity_curve
POST /backtests/compare
  body: { backtest_ids: [...] } → side-by-side metrics for strategy comparison
```

`metrics` includes: total return, annualized return, win rate, profit factor, Sharpe, Sortino, max drawdown, benchmark comparison, average trade return.

## Notes for implementers

- Long-running work (full research run, multi-year backtest) can exceed a normal request budget. For MVP, synchronous with a sensible timeout is fine; design the response shapes so they can move behind a job/polling pattern later (hence `202 { backtest_id }` for backtests).
- Keep route handlers thin: validate → call a service in `app/services/` or the agent orchestrator → map to a response schema.
- Never expose vendor SDK objects directly; always map to internal schemas.

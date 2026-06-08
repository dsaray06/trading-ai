# 04 — Data Model

PostgreSQL via SQLAlchemy ORM + Alembic migrations. Models in `backend/app/models/`. This is the target schema; create it incrementally as phases need it (see `docs/07-roadmap.md`). Use UUID primary keys, `created_at`/`updated_at` timestamps on every table, and foreign-key constraints with sensible `ON DELETE`.

## Entity overview

```
users ──< portfolios ──< positions
                   │
                   ├──< trades
                   └──< recommendations ──< agent_votes
backtests (per user, references a strategy)
securities (reference data, optional cache)
```

## Tables

### users
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| email | text unique | |
| hashed_password | text | null if OAuth-only |
| oauth_provider | text null | e.g. "google" |
| oauth_subject | text null | provider user id |
| created_at / updated_at | timestamptz | |

### portfolios
A user can have several simulated portfolios (e.g. one per strategy). Maps 1:1 to an Alpaca paper account/sub-account when execution is wired up.
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK → users | |
| name | text | |
| starting_cash | numeric(18,2) | |
| cash_balance | numeric(18,2) | current virtual cash |
| alpaca_account_id | text null | paper account linkage |
| created_at / updated_at | timestamptz | |

### positions
Current open holdings (mirrors Alpaca paper positions; refreshed on sync).
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| portfolio_id | uuid FK → portfolios | |
| symbol | text | |
| asset_type | text | stock / etf / option |
| quantity | numeric(18,4) | shares or contracts |
| avg_cost | numeric(18,4) | |
| current_price | numeric(18,4) | last synced mark |
| unrealized_pl | numeric(18,2) | computed |
| opened_at | timestamptz | |
| updated_at | timestamptz | |

### trades
Immutable log of simulated executions.
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| portfolio_id | uuid FK → portfolios | |
| recommendation_id | uuid FK → recommendations null | source rec, if any |
| symbol | text | |
| asset_type | text | stock / etf / option |
| side | text | buy / sell |
| quantity | numeric(18,4) | |
| price | numeric(18,4) | fill price |
| alpaca_order_id | text null | idempotency / reconciliation |
| status | text | filled / pending / canceled / rejected |
| executed_at | timestamptz | |

### recommendations
One row per Trade Decision output. Mirrors `TradeDecision` in `docs/03-agents.md`.
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK → users | |
| portfolio_id | uuid FK → portfolios null | set for holdings reviews |
| symbol | text | |
| asset_type | text | stock / etf / option |
| action | text | Buy / Sell / Hold / Add / Trim / Hedge / Buy Call / Buy Put / Watchlist |
| entry_target | numeric(18,4) null | |
| exit_target | numeric(18,4) null | |
| stop_loss | numeric(18,4) null | |
| take_profit | numeric(18,4) null | |
| position_size | numeric(18,4) null | |
| confidence | numeric(5,2) | 0–100 |
| thesis | text | |
| reasoning_report | text | full explanation |
| created_at | timestamptz | |

### agent_votes
Per-agent breakdown behind a recommendation (powers the "agent vote breakdown" UI).
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| recommendation_id | uuid FK → recommendations | |
| agent | text | market / fundamental / sentiment / options / holdings / risk |
| action | text | this agent's vote |
| score | numeric(5,2) | 0–100 |
| weight | numeric(5,4) | weight used in aggregation |
| reasoning | text | agent's justification |
| raw_output | jsonb | full agent output for the UI/debugging |

### backtests
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK → users | |
| strategy | text | strategy identifier/name |
| params | jsonb | strategy params + agent weights used |
| benchmark | text | SPY / QQQ / VTI / custom |
| horizon | text | 1Y / 3Y / 5Y / 10Y |
| start_date / end_date | date | |
| metrics | jsonb | total/annualized return, win rate, profit factor, Sharpe, Sortino, max drawdown, benchmark-adjusted return, avg trade return |
| equity_curve | jsonb | array of {date, value} for charting |
| created_at | timestamptz | |

### securities (optional reference cache)
Cache of static metadata (name, sector, exchange) to avoid repeated lookups. Not required for MVP.

## Notes

- Use `numeric` (not float) for money/quantities.
- `agent_votes.raw_output` and `backtests.metrics`/`equity_curve` use `jsonb` so the schema can evolve without a migration per metric.
- Idempotency: enforce a unique constraint on `trades.alpaca_order_id` (where not null).
- Soft constraints (risk limits, weights) live in config, not the schema.

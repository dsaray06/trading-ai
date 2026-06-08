# 01 — Product Specification

## Recommendation types

The platform produces recommendations for both new opportunities and existing holdings.

**New opportunities:** Buy Stock, Buy ETF, Buy Call, Buy Put, Hold / Watchlist.

**Existing holdings:** Hold, Add, Trim, Sell, Hedge.

Every recommendation includes an entry target, an exit target (and stop-loss / take-profit where applicable), a position size, a confidence score, and a full reasoning report.

## Example — new opportunity (options)

```
Ticker:          NVDA
Recommendation:  Buy Call
Strike:          $220
Expiration:      45 DTE
Entry Price:     Under $4.20 premium
Position Size:   2 contracts
Risk Allocation: 1.5% portfolio risk
Stop Loss:       -35%
Take Profit:     +60%
Confidence:      74%
Reasoning:
  - Strong earnings momentum
  - Positive sentiment trend
  - High institutional accumulation
  - Bullish technical setup
  - Attractive risk/reward profile
```

## Example — holdings review

```
Ticker:          AAPL
Current Position: 12 shares
Average Cost:     $187.40
Current Price:    $213.20
Unrealized Gain:  +13.8%
Recommendation:   Hold
Confidence:       76%
Reasoning:
  - Strong technical trend
  - Positive fundamentals
  - Positive sentiment
  - Portfolio already heavily weighted toward technology
Suggested Action:
  Maintain current position; consider trimming exposure if price
  closes below support.
```

## Frontend interface

A single-page dashboard with three primary tabs. Built with React + TypeScript + Tailwind; charts via Recharts. See `docs/05-api-spec.md` for the data each view consumes.

### Research tab

Displays, for a searched/selected ticker:

- Trade recommendation (type, targets, sizing, confidence).
- Agent vote breakdown (each agent's vote + score).
- Technical analysis (indicators, trend).
- Fundamental analysis (growth, margins, valuation, health).
- Sentiment analysis (score, catalysts, news summary).
- Options analysis (recommended contracts, Greeks, risk/reward).
- Entry and exit targets.
- Confidence score.
- Full reasoning report.

### Portfolio tab

Displays:

- Portfolio value.
- Virtual cash balance.
- Open positions.
- Allocation breakdown.
- Daily P/L.
- Trade history.
- Benchmark comparison.
- AI recommendations for every holding.
- Portfolio risk metrics.

### Backtesting tab

Displays:

- Strategy selector.
- Backtesting period.
- Equity curve.
- Win rate.
- Sharpe ratio.
- Maximum drawdown.
- Benchmark-adjusted returns.
- Strategy comparison.

## Cross-cutting requirements

- **Disclaimer surface.** A persistent "Research / paper trading only — not financial advice" notice in the UI; the same disclaimer is included in recommendation API responses.
- **Explainability.** No recommendation renders without its agent breakdown and reasoning report available.
- **Loading & error states.** Agent runs take seconds (LLM + data fetch); show progress and degrade gracefully when a data source is unavailable.
- **Auth.** JWT-based sessions; OAuth 2.0 social login. A user owns one or more simulated portfolios.

## Out of scope (for now)

Real-money trading; mobile native apps; multi-user social/sharing features; the strategy marketplace (a future enhancement). See `docs/07-roadmap.md` for what is deferred vs. in-scope per phase.

# 03 — Agent Specifications

This is the heart of the system. Seven agents, orchestrated with LangGraph. Six analysis agents independently evaluate a security and emit scores + a vote; the seventh (Trade Decision) aggregates them into a final recommendation.

## Agent contract (applies to all)

Every agent is a LangGraph node with:

- **Typed input:** a shared `AnalysisContext` (ticker, asset type, the user's portfolio snapshot, requested horizon, and any data already fetched/cached).
- **Typed output:** a Pydantic model specific to the agent (its scores + a `vote`).
- **A vote:** one of the recommendation actions with a 0–100 score, e.g. `{"action": "Buy", "score": 78}`.
- **Reasoning:** a short natural-language justification string the Decision agent can quote.

Scores are normalized 0–100 (higher = more bullish/positive, unless noted). Agents must **never** see future data during a backtest. Agents reason with the Claude API but ground every claim in data fetched from `services.data_sources` — no fabricated numbers.

Implement each agent in `backend/app/agents/<name>.py` with a matching Pydantic output schema in `backend/app/schemas/agents.py`.

---

## 1. Market Analysis Agent

**Responsibilities:** pull historical market data; calculate moving averages, RSI, MACD, Bollinger Bands, volatility metrics; detect trend strength.

**Outputs:** technical score, momentum score, volatility score, trend classification, vote.

```python
class MarketAnalysisOutput(BaseModel):
    technical_score: float        # 0-100
    momentum_score: float         # 0-100
    volatility_score: float       # 0-100, higher = more volatile
    trend: Literal["strong_up", "up", "sideways", "down", "strong_down"]
    indicators: dict              # raw RSI/MACD/MA/BB values for the UI
    vote: AgentVote
    reasoning: str
```

---

## 2. Fundamental Analysis Agent

**Responsibilities:** analyze revenue growth, earnings growth, margins, debt levels, free cash flow, valuation ratios; compare metrics against peers.

**Outputs:** fundamental score, quality score, valuation score, financial-health score, vote.

```python
class FundamentalAnalysisOutput(BaseModel):
    fundamental_score: float
    quality_score: float
    valuation_score: float        # higher = cheaper / better value
    financial_health_score: float
    peer_comparison: dict
    vote: AgentVote
    reasoning: str
```

---

## 3. News & Sentiment Agent

**Responsibilities:** aggregate financial news; summarize recent developments; analyze sentiment; detect catalysts; identify major risks; monitor analyst upgrades/downgrades and earnings releases.

**Outputs:** sentiment score, risk score, catalyst score, news summary, vote.

```python
class SentimentAnalysisOutput(BaseModel):
    sentiment_score: float        # 0-100, higher = more positive
    risk_score: float             # 0-100, higher = more risk
    catalyst_score: float
    news_summary: str
    catalysts: list[str]
    risks: list[str]
    vote: AgentVote
    reasoning: str
```

---

## 4. Options Analysis Agent

**Responsibilities:** evaluate calls and puts; analyze implied volatility and Greeks; calculate expected payoff; compare strikes and expirations; assess liquidity and spreads.

**Outputs:** options score, recommended contracts, strike recommendation, expiration recommendation, risk/reward profile, vote.

```python
class OptionsAnalysisOutput(BaseModel):
    options_score: float
    recommended_contracts: list[dict]   # symbol, type, strike, expiry, premium, greeks
    strike_recommendation: float
    expiration_recommendation: str      # e.g. "45 DTE"
    risk_reward: dict                    # max_gain, max_loss, breakeven, ratio
    vote: AgentVote                      # Buy Call / Buy Put / (n/a for non-options)
    reasoning: str
```

Only runs when the asset/request involves options. For pure equity/ETF research it returns an abstaining vote.

---

## 5. Holdings Review Agent

**Responsibilities (existing positions only):** analyze current positions; compare average cost to market value; calculate unrealized gains/losses; evaluate whether to hold, trim, add, hedge, or sell; detect concentration risk and sector overexposure; recommend rebalancing.

**Outputs:** hold/add/trim/sell/hedge recommendation, position-specific risk score, rebalancing suggestions, vote.

```python
class HoldingsReviewOutput(BaseModel):
    action: Literal["Hold", "Add", "Trim", "Sell", "Hedge"]
    unrealized_pct: float
    position_risk_score: float
    concentration_flags: list[str]      # e.g. "tech > 40% of portfolio"
    rebalancing_suggestions: list[str]
    vote: AgentVote
    reasoning: str
```

Runs in the holdings-review flow (a position the user already owns), not in new-opportunity research.

---

## 6. Portfolio Risk Agent

**Responsibilities:** calculate position sizing; enforce portfolio risk limits; set stop-loss and take-profit targets; prevent overexposure; manage sector allocation and concentration.

**Outputs:** position size, risk allocation, portfolio exposure, maximum-loss estimate, vote.

```python
class PortfolioRiskOutput(BaseModel):
    position_size: float                 # shares or contracts
    risk_allocation_pct: float           # e.g. 1.5 (% of portfolio at risk)
    stop_loss: float
    take_profit: float
    portfolio_exposure: dict             # post-trade sector/asset exposure
    max_loss_estimate: float
    vote: AgentVote                      # can veto/downgrade if limits breached
    reasoning: str
```

The risk agent can **constrain** the final recommendation (e.g. force a smaller size or downgrade Buy→Hold if limits would be breached).

---

## 7. Trade Decision Agent

**Responsibilities:** combine outputs from all agents; weight their recommendations; generate the final recommendation; create an investment thesis; assign a confidence score.

**Outputs:** final action (Buy / Sell / Hold / Add / Trim / Hedge), entry target, exit target, confidence score, full reasoning report.

```python
class TradeDecision(BaseModel):
    ticker: str
    action: Literal["Buy", "Sell", "Hold", "Add", "Trim", "Hedge",
                    "Buy Call", "Buy Put", "Buy ETF", "Watchlist"]
    entry_target: float | None
    exit_target: float | None
    stop_loss: float | None
    take_profit: float | None
    position_size: float | None
    confidence: float                    # 0-100
    agent_votes: list[AgentVote]
    thesis: str                          # the investment thesis
    reasoning_report: str                # full human-readable explanation
    disclaimer: str = "Research / paper trading only. Not financial advice."
```

---

## Agent voting system

Each specialized agent independently evaluates a security and casts a vote with a 0–100 score. The Trade Decision agent produces the final call through **weighted voting and confidence aggregation**.

**Worked example:**

```
Market Agent:       Buy  (78)
Fundamental Agent:  Buy  (84)
Sentiment Agent:    Hold (60)
Options Agent:      Buy  (82)
Risk Agent:         Hold (65)

Final Decision Agent:
  Action:     Buy
  Confidence: 74%
```

### Aggregation algorithm (reference)

Make this a pure, unit-tested function — `app/agents/decision.py::aggregate_votes`. Suggested approach:

1. **Map actions to a directional axis** (e.g. Sell = -1, Trim/Hedge = -0.5, Hold/Watchlist = 0, Add = +0.5, Buy/Buy Call = +1; Buy Put is bearish).
2. **Weight each agent.** Start with configurable weights (e.g. fundamental 0.25, market 0.20, sentiment 0.15, options 0.15, risk 0.15, holdings 0.10). Weights live in config so they can be tuned/backtested.
3. **Compute a weighted directional score** = Σ(weight · direction · score/100).
4. **Apply risk constraints.** The Risk agent can cap position size or downgrade the action if limits are breached (hard guardrail, not just a vote).
5. **Map the aggregate back to a discrete action** via thresholds.
6. **Confidence** = a function of (a) agreement among agents (low variance → higher confidence) and (b) the magnitude of the weighted score. Document the exact formula in the docstring and test it.

Determinism: given the same agent outputs and weights, `aggregate_votes` must always return the same decision. The LLM is used for *reasoning prose*, not for the numeric aggregation.

## Shared types

Put these in `app/schemas/agents.py`:

```python
class AgentVote(BaseModel):
    agent: str                  # e.g. "market"
    action: str                 # Buy / Sell / Hold / ...
    score: float                # 0-100
    weight: float = 0.0         # filled by the orchestrator
    abstain: bool = False
```

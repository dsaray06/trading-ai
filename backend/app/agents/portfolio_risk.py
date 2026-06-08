"""Portfolio Risk agent.

Computes portfolio-level risk metrics deterministically: exposure by symbol,
concentration, cash buffer, and an overall risk score. Also provides position
sizing for a prospective trade (a simple fixed-fractional rule with a per-trade
risk cap). No LLM — these are reproducible numbers (docs/03-agents.md §6).
"""
from __future__ import annotations

from dataclasses import dataclass

# Default risk policy (would live in config for tuning/backtesting).
MAX_POSITION_PCT = 0.25  # cap a single new position at 25% of portfolio value
PER_TRADE_RISK_PCT = 0.02  # risk ~2% of portfolio per trade to the stop
DEFAULT_STOP_PCT = 0.08  # 8% stop if none supplied


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


@dataclass(frozen=True)
class HoldingExposure:
    symbol: str
    market_value: float


def portfolio_risk_metrics(
    holdings: list[HoldingExposure], cash: float, total_value: float
) -> dict:
    """Exposure, concentration, cash buffer, and a 0-100 risk score."""
    if total_value <= 0:
        return {
            "total_value": round(total_value, 2),
            "invested_pct": 0.0,
            "cash_pct": 100.0,
            "largest_position_pct": 0.0,
            "num_positions": 0,
            "exposure": {},
            "risk_score": 0.0,
        }

    exposure = {
        h.symbol: round(h.market_value / total_value * 100.0, 2) for h in holdings
    }
    invested = sum(h.market_value for h in holdings)
    largest = max((h.market_value for h in holdings), default=0.0) / total_value
    invested_pct = invested / total_value

    # More concentrated + more fully invested => higher risk.
    risk_score = _clamp(20.0 + largest * 80.0 + invested_pct * 20.0)
    return {
        "total_value": round(total_value, 2),
        "invested_pct": round(invested_pct * 100.0, 2),
        "cash_pct": round(cash / total_value * 100.0, 2),
        "largest_position_pct": round(largest * 100.0, 2),
        "num_positions": len(holdings),
        "exposure": exposure,
        "risk_score": round(risk_score, 2),
    }


def position_size(
    price: float,
    portfolio_value: float,
    stop_loss: float | None = None,
    cash_available: float | None = None,
) -> dict:
    """Shares to buy under a fixed-fractional rule + a max-position cap.

    Returns size (shares), the stop used, and the estimated max loss to the stop.
    """
    if price <= 0 or portfolio_value <= 0:
        return {"shares": 0.0, "stop_loss": None, "max_loss_estimate": 0.0,
                "risk_allocation_pct": 0.0}

    stop = stop_loss if stop_loss and 0 < stop_loss < price else price * (1 - DEFAULT_STOP_PCT)
    risk_per_share = max(price - stop, price * DEFAULT_STOP_PCT)
    risk_budget = portfolio_value * PER_TRADE_RISK_PCT
    shares_by_risk = risk_budget / risk_per_share
    shares_by_cap = (portfolio_value * MAX_POSITION_PCT) / price
    shares = min(shares_by_risk, shares_by_cap)
    if cash_available is not None:
        shares = min(shares, cash_available / price)
    shares = max(0.0, float(int(shares)))  # whole shares

    max_loss = shares * risk_per_share
    return {
        "shares": shares,
        "stop_loss": round(stop, 2),
        "max_loss_estimate": round(max_loss, 2),
        "risk_allocation_pct": round(max_loss / portfolio_value * 100.0, 2),
    }

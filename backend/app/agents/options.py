"""Options Analysis agent.

Picks a directional option (call if bullish, put if bearish), selects a strike
and expiration from the chain, computes Greeks via Black-Scholes (yfinance gives
IV but not Greeks), and builds a risk/reward profile. Numbers are deterministic;
the explanation is LLM-written with a templated fallback. Votes Buy Call / Buy
Put, or abstains when options aren't requested/available (docs/03-agents.md §4).
"""
from __future__ import annotations

from app.core.llm import get_llm_client
from app.schemas.agents import AgentVote, OptionsAnalysisOutput
from app.services.data_sources.base import OptionChain, OptionContract
from app.services.options_math import option_metrics

AGENT_NAME = "options"

RISK_FREE_RATE = 0.04
_FALLBACK_IV = 0.40        # used when a contract has no implied vol
_TARGET_MOVE = 0.15        # assumed favorable underlying move for max-gain estimate
_STOP_FRACTION = 0.50      # exit at -50% of premium
_TAKE_FRACTION = 2.00      # target +100% of premium

_SYSTEM_PROMPT = (
    "You are the Options Analysis agent in a paper-trading platform. In 2-3 sentences, "
    "explain a single recommended option trade to a retail investor, grounded strictly in "
    "the strike, expiration, premium, Greeks, and risk/reward provided; never invent numbers. "
    "Respond in plain text only: no Markdown, no headings, no bullet points."
)


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _select_contract(contracts: list[OptionContract], spot: float, opt_type: str) -> OptionContract:
    """Pick a slightly out-of-the-money contract nearest a 5% OTM target."""
    if opt_type == "call":
        pool = [c for c in contracts if c.strike >= spot] or contracts
        target = spot * 1.05
    else:
        pool = [c for c in contracts if c.strike <= spot] or contracts
        target = spot * 0.95
    return min(pool, key=lambda c: abs(c.strike - target))


def _abstain(reason: str) -> OptionsAnalysisOutput:
    vote = AgentVote(agent=AGENT_NAME, action="Hold", score=50.0, abstain=True,
                     reasoning=reason)
    return OptionsAnalysisOutput(
        options_score=50.0, recommended_contracts=[], strike_recommendation=0.0,
        expiration_recommendation="n/a", risk_reward={}, contract_symbol="",
        premium=0.0, greeks={}, vote=vote, reasoning=reason,
    )


def run_options_agent(
    ticker: str, chain: OptionChain, bullish: bool, strength: float = 50.0
) -> OptionsAnalysisOutput:
    """Build a Buy Call / Buy Put recommendation from an option chain."""
    opt_type = "call" if bullish else "put"
    action = "Buy Call" if bullish else "Buy Put"
    contracts = chain.calls if bullish else chain.puts
    if not contracts:
        return _abstain(f"No {opt_type}s available for {ticker}; abstaining.")

    contract = _select_contract(contracts, chain.spot, opt_type)
    iv = contract.implied_volatility if (contract.implied_volatility or 0) > 0 else _FALLBACK_IV
    t = max(chain.dte, 1) / 365.0
    m = option_metrics(chain.spot, contract.strike, t, RISK_FREE_RATE, iv, opt_type)

    premium = contract.premium
    multiplier = 100
    max_loss = round(premium * multiplier, 2)
    if opt_type == "call":
        target_spot = chain.spot * (1 + _TARGET_MOVE)
        target_payoff = max(0.0, target_spot - contract.strike)
    else:
        target_spot = chain.spot * (1 - _TARGET_MOVE)
        target_payoff = max(0.0, contract.strike - target_spot)
    max_gain = round(target_payoff * multiplier - premium * multiplier, 2)
    ratio = round(max_gain / max_loss, 2) if max_loss > 0 else 0.0

    greeks = {k: round(v, 4) for k, v in {
        "delta": m.delta, "gamma": m.gamma, "theta": m.theta,
        "vega": m.vega, "rho": m.rho,
    }.items()}
    risk_reward = {
        "max_gain": max_gain, "max_loss": max_loss,
        "breakeven": round(m.breakeven, 2), "ratio": ratio,
        "target_underlying": round(target_spot, 2),
    }
    rr_component = _clamp(ratio / 3.0 * 100.0)
    liq = float(contract.open_interest or 0)
    liq_component = _clamp(liq / 1000.0 * 100.0)
    options_score = round(_clamp(0.5 * strength + 0.3 * rr_component + 0.2 * liq_component), 2)

    contract_symbol = contract.contract_symbol or _synth_symbol(
        ticker, contract, opt_type
    )
    recommended = [{
        "contract_symbol": contract_symbol, "type": opt_type, "strike": contract.strike,
        "expiry": chain.expiry.isoformat(), "dte": chain.dte, "premium": premium,
        "implied_volatility": round(iv, 4), "open_interest": contract.open_interest,
        "volume": contract.volume, "greeks": greeks,
    }]
    expiration = f"{chain.dte} DTE ({chain.expiry.isoformat()})"

    reasoning = get_llm_client().generate_reasoning(
        system=_SYSTEM_PROMPT,
        prompt=(
            f"Underlying: {ticker} at ${chain.spot:.2f} ({'bullish' if bullish else 'bearish'}).\n"
            f"Recommended: {action} {contract.strike} strike, {expiration}, premium "
            f"${premium:.2f}, IV {iv:.0%}, delta {m.delta:.2f}, breakeven "
            f"${m.breakeven:.2f}. Risk/reward: {risk_reward}.\nWrite the explanation."
        ),
        max_tokens=300,
    )
    if reasoning is None:
        reasoning = (
            f"{action} on {ticker}: the {contract.strike} strike expiring in {chain.dte} "
            f"days costs ${premium:.2f} (IV {iv:.0%}, delta {m.delta:.2f}), with a breakeven "
            f"of ${m.breakeven:.2f} and a ~{ratio:.1f}:1 reward/risk on a {_TARGET_MOVE:.0%} move."
        )

    vote = AgentVote(agent=AGENT_NAME, action=action, score=options_score, reasoning=reasoning)
    return OptionsAnalysisOutput(
        options_score=options_score,
        recommended_contracts=recommended,
        strike_recommendation=contract.strike,
        expiration_recommendation=expiration,
        risk_reward=risk_reward,
        contract_symbol=contract_symbol,
        premium=premium,
        stop_loss=round(premium * _STOP_FRACTION, 2),
        take_profit=round(premium * _TAKE_FRACTION, 2),
        contracts=1,
        greeks=greeks,
        implied_volatility=round(iv, 4),
        vote=vote,
        reasoning=reasoning,
    )


def _synth_symbol(ticker: str, contract: OptionContract, opt_type: str) -> str:
    """OCC-style fallback symbol when the provider didn't supply one."""
    yymmdd = contract.expiry.strftime("%y%m%d")
    cp = "C" if opt_type == "call" else "P"
    strike_milli = int(round(contract.strike * 1000))
    return f"{ticker}{yymmdd}{cp}{strike_milli:08d}"

"""Trade Decision agent.

Combines the analysis agents' votes into a final recommendation. The numbers
(action, confidence, weights) come from the pure, tested `aggregate_votes`; the
investment thesis and reasoning report are written by Claude, synthesizing the
agents' views (templated fallback when the LLM is unavailable). The LLM never
decides the action — it explains the aggregated one (docs/03-agents.md).
"""
from __future__ import annotations

from app.agents.decision import aggregate_votes, normalized_weights
from app.core.llm import get_llm_client
from app.schemas.agents import AgentVote, TradeDecision

AGENT_NAME = "decision"

_SYSTEM_PROMPT = (
    "You are the Trade Decision agent in a paper-trading research platform. "
    "You synthesize several specialist agents' votes into one explanation for a retail "
    "investor. The final action and confidence are already decided by a deterministic "
    "vote aggregator — do NOT change them; explain why they follow from the agents' views. "
    "Ground everything in the agents' reasoning; never invent numbers. "
    "Respond in plain text only (no Markdown) in exactly this format:\n"
    "THESIS: <one sentence>\n"
    "REPORT: <3-4 sentences>"
)


def _parse_prose(text: str) -> tuple[str | None, str | None]:
    """Pull THESIS/REPORT out of the model's reply; tolerate minor format drift."""
    thesis: str | None = None
    report: str | None = None
    current: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("THESIS:"):
            thesis = stripped[len("THESIS:"):].strip()
            current = "thesis"
        elif upper.startswith("REPORT:"):
            report = stripped[len("REPORT:"):].strip()
            current = "report"
        elif stripped and current == "report":
            report = f"{report} {stripped}".strip() if report else stripped
        elif stripped and current == "thesis" and not report:
            thesis = f"{thesis} {stripped}".strip() if thesis else stripped
    return thesis or None, report or None


def _fallback_thesis(action: str, confidence: float, participating: int) -> str:
    return (f"{participating} agent(s) analyzed this security; the aggregated call is "
            f"{action} at {confidence:.0f}% confidence.")


def _fallback_report(votes: list[AgentVote]) -> str:
    parts = []
    for v in votes:
        tag = "abstained" if v.abstain else f"{v.action} ({v.score:.0f})"
        parts.append(f"{v.agent.capitalize()}: {tag}")
    return "Agent breakdown — " + "; ".join(parts) + "."


def decide(
    ticker: str,
    votes: list[AgentVote],
    asset_type: str = "stock",
    weights: dict[str, float] | None = None,
    reference_price: float | None = None,
    options: dict | None = None,
) -> TradeDecision:
    """Aggregate votes (deterministic) and write the thesis/report (LLM + fallback).

    When `options` is provided (a non-abstaining Options agent result), the final
    *action* is the options call (Buy Call / Buy Put) and entry/stop/take/size come
    from the contract — but confidence still reflects the full agent vote.
    """
    agg = aggregate_votes(votes, weights)
    norm = normalized_weights(votes, weights)
    for v in votes:
        v.weight = round(norm.get(v.agent, 0.0), 4)

    # Options-driven recommendation overrides the equity action with the contract.
    action = agg.action
    entry_target = reference_price
    stop_loss = take_profit = position_size = None
    if options and options.get("action") in ("Buy Call", "Buy Put"):
        action = options["action"]
        entry_target = options.get("premium")
        stop_loss = options.get("stop_loss")
        take_profit = options.get("take_profit")
        position_size = options.get("contracts")

    vote_lines = "\n".join(
        f"- {v.agent}: {'ABSTAIN' if v.abstain else v.action} "
        f"(score {v.score:.0f}, weight {v.weight:.2f}) — {v.reasoning[:240]}"
        for v in votes
    )
    options_note = ""
    if options and action in ("Buy Call", "Buy Put"):
        options_note = (
            f"\nThis is an OPTIONS trade: {action} the {options.get('strike')} strike "
            f"({options.get('expiration')}) at ${options.get('premium')} premium."
        )
    prose = get_llm_client().generate_reasoning(
        system=_SYSTEM_PROMPT,
        prompt=(
            f"Ticker: {ticker} ({asset_type})\n"
            f"Agent votes:\n{vote_lines}\n\n"
            f"Aggregated decision (fixed): {action} at {agg.confidence:.0f}% confidence "
            f"(weighted score {agg.weighted_score}).{options_note} Explain it."
        ),
        max_tokens=400,
    )

    thesis, report = (None, None)
    if prose is not None:
        thesis, report = _parse_prose(prose)
    if thesis is None:
        thesis = _fallback_thesis(action, agg.confidence, agg.participating)
    if report is None:
        report = prose.strip() if prose else _fallback_report(votes)

    return TradeDecision(
        ticker=ticker,
        asset_type="option" if action in ("Buy Call", "Buy Put") else asset_type,
        action=action,
        entry_target=entry_target,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size=position_size,
        confidence=agg.confidence,
        agent_votes=votes,
        thesis=thesis,
        reasoning_report=report,
    )

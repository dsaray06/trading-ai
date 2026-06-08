"""Trade Decision agent: vote aggregation + final recommendation.

`aggregate_votes` is the deterministic heart of the system (docs/03-agents.md).
Given identical agent votes and weights it always returns the same action,
confidence, and weighted score. The LLM is used only for the thesis/report prose,
never for these numbers.

Aggregation (documented so it can be tested against fixed inputs):

1. Map each action to a direction on [-1, 1]:
   Sell / Buy Put = -1, Trim / Hedge = -0.5, Hold / Watchlist = 0,
   Add = +0.5, Buy / Buy Call / Buy ETF = +1.
2. Each agent has a weight from `DEFAULT_WEIGHTS`; abstaining agents are dropped.
   Weights are renormalized over participating agents so they sum to 1.
3. weighted_score = Σ(weight_i · direction_i · score_i/100)   ∈ [-1, 1].
4. (Risk constraints applied by the Risk agent arrive in Phase 3.)
5. Map weighted_score back to a discrete action via thresholds.
6. Confidence ∈ [0, 100] = 100 · (0.4·agreement + 0.3·|weighted_score| +
   0.3·avg_conviction), where:
     - agreement   = 1 − (stdev of directions)/1  (1.0 when agents align; lower
                     when they pull in opposite directions),
     - avg_conviction = weighted mean of score_i/100 (how sure each agent is).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from app.schemas.agents import Action, AgentVote

# Default agent weights (docs/03-agents.md). Tunable; backtested later.
DEFAULT_WEIGHTS: dict[str, float] = {
    "fundamental": 0.25,
    "market": 0.20,
    "sentiment": 0.15,
    "options": 0.15,
    "risk": 0.15,
    "holdings": 0.10,
}

_DIRECTION: dict[str, float] = {
    "Sell": -1.0,
    "Buy Put": -1.0,
    "Trim": -0.5,
    "Hedge": -0.5,
    "Hold": 0.0,
    "Watchlist": 0.0,
    "Add": 0.5,
    "Buy": 1.0,
    "Buy Call": 1.0,
    "Buy ETF": 1.0,
}


@dataclass(frozen=True)
class Aggregation:
    action: Action
    confidence: float          # 0-100
    weighted_score: float      # -1..1
    participating: int


def normalized_weights(
    votes: list[AgentVote], weights: dict[str, float] | None = None
) -> dict[str, float]:
    """Renormalized weights actually used in aggregation, keyed by agent.

    Mirrors the weighting in `aggregate_votes` so the UI can show the same numbers.
    Abstaining agents get 0.
    """
    weights = weights or DEFAULT_WEIGHTS
    active = [v for v in votes if not v.abstain]
    raw = {v.agent: weights.get(v.agent, 0.0) for v in active}
    total = sum(raw.values())
    if total == 0:
        if not active:
            return {}
        equal = 1.0 / len(active)
        return {v.agent: equal for v in active}
    return {agent: w / total for agent, w in raw.items()}


def _action_from_score(score: float) -> Action:
    if score >= 0.50:
        return "Buy"
    if score >= 0.15:
        return "Add"
    if score > -0.15:
        return "Hold"
    if score > -0.50:
        return "Trim"
    return "Sell"


def aggregate_votes(
    votes: list[AgentVote], weights: dict[str, float] | None = None
) -> Aggregation:
    """Aggregate agent votes into a final action + confidence. Pure & deterministic."""
    weights = weights or DEFAULT_WEIGHTS
    active = [v for v in votes if not v.abstain]
    if not active:
        return Aggregation(action="Watchlist", confidence=0.0, weighted_score=0.0,
                           participating=0)

    raw_weights = [weights.get(v.agent, 0.0) for v in active]
    total = sum(raw_weights)
    # If no configured weights matched, fall back to equal weighting.
    if total == 0:
        raw_weights = [1.0 for _ in active]
        total = float(len(active))
    norm = [w / total for w in raw_weights]

    directions = [_DIRECTION.get(v.action, 0.0) for v in active]
    weighted_score = sum(
        w * d * (v.score / 100.0) for w, d, v in zip(norm, directions, active, strict=True)
    )
    action = _action_from_score(weighted_score)

    agreement = 1.0 - (statistics.pstdev(directions) if len(directions) > 1 else 0.0)
    agreement = max(0.0, min(1.0, agreement))
    avg_conviction = sum(w * (v.score / 100.0) for w, v in zip(norm, active, strict=True))
    confidence = 100.0 * (
        0.4 * agreement + 0.3 * abs(weighted_score) + 0.3 * avg_conviction
    )

    return Aggregation(
        action=action,
        confidence=round(max(0.0, min(100.0, confidence)), 2),
        weighted_score=round(weighted_score, 4),
        participating=len(active),
    )

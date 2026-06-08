"""Unit tests for the deterministic vote aggregation."""
from __future__ import annotations

import pytest

from app.agents import decision
from app.schemas.agents import AgentVote


def test_single_buy_passthrough():
    agg = decision.aggregate_votes([AgentVote(agent="market", action="Buy", score=80)])
    assert agg.action == "Buy"
    assert agg.weighted_score == pytest.approx(0.8)
    # agreement=1, magnitude=0.8, avg_conviction=0.8 -> 100*(0.4+0.24+0.24)
    assert agg.confidence == pytest.approx(88.0, abs=0.01)
    assert agg.participating == 1


def test_single_hold_has_zero_direction():
    agg = decision.aggregate_votes([AgentVote(agent="market", action="Hold", score=60)])
    assert agg.action == "Hold"
    assert agg.weighted_score == pytest.approx(0.0)
    assert agg.confidence == pytest.approx(58.0, abs=0.01)


def test_disagreement_pulls_toward_hold_and_low_confidence():
    votes = [
        AgentVote(agent="market", action="Buy", score=80),
        AgentVote(agent="sentiment", action="Sell", score=80),
    ]
    agg = decision.aggregate_votes(votes)
    assert agg.action == "Hold"
    assert abs(agg.weighted_score) < 0.15
    # opposing directions -> agreement 0 -> low confidence
    assert agg.confidence < 35


def test_all_abstain_returns_watchlist():
    votes = [AgentVote(agent="options", action="Hold", score=0, abstain=True)]
    agg = decision.aggregate_votes(votes)
    assert agg.action == "Watchlist"
    assert agg.confidence == 0.0
    assert agg.participating == 0


def test_normalized_weights_single_agent_sums_to_one():
    votes = [AgentVote(agent="market", action="Buy", score=70)]
    w = decision.normalized_weights(votes)
    assert w["market"] == pytest.approx(1.0)


def test_determinism():
    votes = [AgentVote(agent="market", action="Buy", score=73.5)]
    assert decision.aggregate_votes(votes) == decision.aggregate_votes(votes)

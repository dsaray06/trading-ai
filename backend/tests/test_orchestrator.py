"""Integration tests for the LangGraph orchestrator (offline, fake sources)."""
from __future__ import annotations

from app.agents.orchestrator import run_pipeline
from tests.fakes import (
    FailingSource,
    FakeFundamentalsSource,
    FakeNewsSource,
    FakeOptionsSource,
    FakeUptrendSource,
)


def _run(include_options=False):
    return run_pipeline(
        "TEST", "stock", FakeUptrendSource(), FakeFundamentalsSource(),
        FakeNewsSource(), FakeOptionsSource(), include_options=include_options,
    )


def test_analysis_agents_vote_and_decision_is_bullish():
    decision, analysis = _run()
    agents = {v.agent for v in decision.agent_votes}
    assert agents == {"market", "fundamental", "sentiment", "options"}
    # Options abstains when not requested; the other three vote.
    voting = [v for v in decision.agent_votes if not v.abstain]
    assert {v.agent for v in voting} == {"market", "fundamental", "sentiment"}
    assert decision.action in {"Buy", "Add"}
    assert 0 < decision.confidence <= 100
    assert {"technical", "fundamental", "sentiment"} <= set(analysis.keys())
    assert abs(sum(v.weight for v in voting) - 1.0) < 1e-6


def test_options_requested_yields_call_recommendation():
    decision, analysis = _run(include_options=True)
    by_agent = {v.agent: v for v in decision.agent_votes}
    assert by_agent["options"].abstain is False
    # Uptrend -> bullish -> Buy Call drives the final action.
    assert decision.action == "Buy Call"
    assert decision.entry_target == 5.0  # premium
    assert "options" in analysis and analysis["options"]["strike"] > 0


def test_failing_source_abstains_but_run_succeeds():
    decision, _ = run_pipeline(
        "TEST", "stock", FakeUptrendSource(), FailingSource(),
        FakeNewsSource(), FakeOptionsSource(),
    )
    by_agent = {v.agent: v for v in decision.agent_votes}
    assert by_agent["fundamental"].abstain is True
    assert by_agent["fundamental"].weight == 0.0
    assert by_agent["market"].abstain is False
    assert decision.action


def test_determinism_of_decision():
    d1, _ = _run()
    d2, _ = _run()
    assert (d1.action, d1.confidence) == (d2.action, d2.confidence)

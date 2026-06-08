"""News & Sentiment agent.

Scores sentiment deterministically from two structured signals — analyst rating
distribution and a lexicon pass over recent headlines — then writes a prose news
summary via the LLM (templated fallback offline). Abstains when neither signal is
available (docs/03-agents.md, docs/06).

The numeric scores are reproducible; only the `news_summary` prose comes from the
LLM, consistent with the project's determinism rule.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.llm import get_llm_client
from app.schemas.agents import AgentVote, SentimentAnalysisOutput
from app.services.data_sources.base import AnalystRecommendations, SentimentData

AGENT_NAME = "sentiment"

_SYSTEM_PROMPT = (
    "You are the News & Sentiment agent in a paper-trading research platform. "
    "Summarize the recent news tone for a stock in 2-3 sentences for a retail investor, "
    "using only the headlines provided; never invent events. Be concise and neutral. "
    "Respond in plain text only: no Markdown, no headings, no bullet points."
)

_POSITIVE = {
    "beat", "beats", "surge", "surges", "upgrade", "upgraded", "growth", "record",
    "strong", "rally", "gains", "gain", "outperform", "raises", "raised", "jumps",
    "soars", "bullish", "profit", "wins", "win", "tops", "boost", "boosted", "higher",
    "rises", "rose", "expands", "rebound", "optimistic",
}
_NEGATIVE = {
    "miss", "misses", "plunge", "plunges", "downgrade", "downgraded", "lawsuit",
    "decline", "declines", "weak", "cuts", "cut", "falls", "fell", "drops", "drop",
    "slumps", "bearish", "probe", "recall", "warning", "loss", "losses", "sinks",
    "tumbles", "lower", "concerns", "slash", "halts", "investigation", "fraud",
}
_CATALYST = {
    "earnings", "upgrade", "downgrade", "guidance", "launch", "deal", "merger",
    "acquisition", "partnership", "approval", "contract", "dividend", "buyback",
    "fda", "lawsuit", "settlement", "ipo",
}
_RISK_WORDS = {
    "lawsuit", "probe", "investigation", "recall", "warning", "downgrade", "miss",
    "loss", "concerns", "halts", "slash", "cuts", "decline", "weak", "fraud",
}

_ANALYST_WEIGHTS = {"strong_buy": 100.0, "buy": 75.0, "hold": 50.0,
                    "sell": 25.0, "strong_sell": 0.0}


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def _analyst_score(a: AnalystRecommendations) -> float | None:
    if a.total == 0:
        return None
    counts = {"strong_buy": a.strong_buy, "buy": a.buy, "hold": a.hold,
              "sell": a.sell, "strong_sell": a.strong_sell}
    return sum(_ANALYST_WEIGHTS[k] * n for k, n in counts.items()) / a.total


@dataclass(frozen=True)
class SentimentScores:
    sentiment: float | None
    risk: float
    catalyst: float
    headline_net: int  # sum of (positive - negative) word hits across headlines
    catalysts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


def score_sentiment(data: SentimentData) -> SentimentScores:
    """Deterministic sentiment/risk/catalyst scores from analysts + headlines."""
    analyst = _analyst_score(data.analysts) if data.analysts else None

    news = data.news
    net_total = 0
    neg_headlines = 0
    catalyst_hits = 0
    catalysts: list[str] = []
    risks: list[str] = []
    for item in news:
        toks = set(_tokens(item.title))
        pos = len(toks & _POSITIVE)
        neg = len(toks & _NEGATIVE)
        net_total += pos - neg
        if neg > pos:
            neg_headlines += 1
        if toks & _CATALYST:
            catalyst_hits += 1
            if len(catalysts) < 3:
                catalysts.append(item.title)
        if toks & _RISK_WORDS and len(risks) < 3:
            risks.append(item.title)

    news_score: float | None = None
    if news:
        avg_net = net_total / len(news)
        news_score = _clamp(50.0 + avg_net * 25.0)

    available = [s for s in (analyst, news_score) if s is not None]
    sentiment = sum(available) / len(available) if available else None

    n = max(1, len(news))
    neg_ratio = neg_headlines / n
    sell_ratio = 0.0
    if data.analysts and data.analysts.total:
        sell_ratio = (data.analysts.sell + data.analysts.strong_sell) / data.analysts.total
    risk = _clamp(30.0 + 70.0 * max(neg_ratio, sell_ratio))
    catalyst = _clamp(20.0 + 80.0 * (catalyst_hits / n)) if news else 0.0

    return SentimentScores(
        sentiment=sentiment, risk=round(risk, 2), catalyst=round(catalyst, 2),
        headline_net=net_total, catalysts=catalysts, risks=risks,
    )


def _action_for_score(score: float) -> str:
    if score >= 58:
        return "Buy"
    if score > 40:
        return "Hold"
    return "Sell"


def _abstain(reason: str) -> SentimentAnalysisOutput:
    vote = AgentVote(agent=AGENT_NAME, action="Hold", score=50.0, abstain=True,
                     reasoning=reason)
    return SentimentAnalysisOutput(
        sentiment_score=50.0, risk_score=50.0, catalyst_score=0.0, news_summary=reason,
        catalysts=[], risks=[], vote=vote, reasoning=reason,
    )


def _template_summary(ticker: str, data: SentimentData, s: SentimentScores) -> str:
    tone = "positive" if s.headline_net > 0 else "negative" if s.headline_net < 0 else "mixed"
    analyst_note = ""
    if data.analysts and data.analysts.total:
        a = data.analysts
        analyst_note = (f" Analysts: {a.strong_buy + a.buy} buy / {a.hold} hold / "
                        f"{a.sell + a.strong_sell} sell.")
    return (
        f"{ticker} has {len(data.news)} recent headlines with a net {tone} tone "
        f"(sentiment {s.sentiment or 50:.0f}/100, risk {s.risk:.0f}/100).{analyst_note}"
    )


def run_sentiment_agent(ticker: str, data: SentimentData) -> SentimentAnalysisOutput:
    """Score sentiment and emit a vote + news summary, abstaining if no signal."""
    s = score_sentiment(data)
    if s.sentiment is None:
        return _abstain(f"No news or analyst sentiment available for {ticker}; abstaining.")

    action = _action_for_score(s.sentiment)
    headlines = [item.title for item in data.news[:10]]
    summary = get_llm_client().generate_reasoning(
        system=_SYSTEM_PROMPT,
        prompt=(
            f"Ticker: {ticker}\n"
            f"Recent headlines: {headlines}\n"
            f"Computed scores -> sentiment: {s.sentiment:.1f}, risk: {s.risk}, "
            f"catalyst: {s.catalyst}, leaning: {action}.\nWrite the news summary."
        ),
        max_tokens=300,
    )
    if summary is None:
        summary = _template_summary(ticker, data, s)

    vote = AgentVote(agent=AGENT_NAME, action=action, score=round(s.sentiment, 2),
                     reasoning=summary)
    return SentimentAnalysisOutput(
        sentiment_score=round(s.sentiment, 2),
        risk_score=s.risk,
        catalyst_score=s.catalyst,
        news_summary=summary,
        catalysts=s.catalysts,
        risks=s.risks,
        vote=vote,
        reasoning=summary,
    )

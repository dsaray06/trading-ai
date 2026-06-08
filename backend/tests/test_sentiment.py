"""Unit tests for the News & Sentiment agent's deterministic scoring."""
from __future__ import annotations

import pytest

from app.agents.sentiment import run_sentiment_agent, score_sentiment
from app.services.data_sources.base import AnalystRecommendations, NewsItem, SentimentData


def _news(*titles: str) -> list[NewsItem]:
    return [NewsItem(title=t) for t in titles]


def test_bullish_news_and_analysts_scores_high_and_buys():
    data = SentimentData(
        news=_news(
            "Company beats earnings and raises guidance",
            "Analysts upgrade on strong revenue growth",
        ),
        analysts=AnalystRecommendations(strong_buy=5, buy=10, hold=3, sell=1),
    )
    s = score_sentiment(data)
    assert s.sentiment > 70
    assert s.risk < 50
    assert s.catalyst > 50  # earnings/upgrade detected
    assert run_sentiment_agent("X", data).vote.action == "Buy"


def test_bearish_news_and_analysts_scores_low_and_sells():
    data = SentimentData(
        news=_news(
            "Stock plunges after earnings miss and downgrade",
            "Lawsuit and probe weigh on shares",
        ),
        analysts=AnalystRecommendations(buy=1, hold=2, sell=6, strong_sell=8),
    )
    s = score_sentiment(data)
    assert s.sentiment < 30
    assert s.risk > 80
    assert "downgrade" in " ".join(s.risks).lower() or "lawsuit" in " ".join(s.risks).lower()
    assert run_sentiment_agent("Y", data).vote.action == "Sell"


def test_analyst_only_still_scores():
    data = SentimentData(analysts=AnalystRecommendations(strong_buy=8, buy=2))
    s = score_sentiment(data)
    assert s.sentiment == pytest.approx(95.0)  # (100*8 + 75*2)/10


def test_no_signal_abstains():
    out = run_sentiment_agent("Z", SentimentData())
    assert out.vote.abstain is True


def test_neutral_when_empty_news_and_no_analysts():
    s = score_sentiment(SentimentData())
    assert s.sentiment is None
    assert s.catalyst == 0.0

# 00 — Project Overview

## Summary

Trading AI is a full-stack, multi-agent paper-trading and investment-research platform that analyzes stocks, ETFs, options, and portfolio holdings using market data, company fundamentals, technical indicators, news sentiment, and large language models.

The platform generates AI-powered investment research, evaluates new opportunities, analyzes existing portfolio positions, produces structured trade recommendations, executes simulated trades through Alpaca's paper-trading API, tracks portfolio performance, and continuously evaluates strategies through historical backtesting.

Unlike a traditional stock screener or trading dashboard, Trading AI functions as an AI-powered investment analyst capable of researching securities, evaluating risk, sizing positions, generating trade theses, managing a simulated portfolio, and recommending actions on both current holdings and potential investments.

**The platform is for research and paper trading only. It does not execute real-money trades.**

## Goals

### Technical goals

- Build a production-grade full-stack application.
- Implement multi-agent orchestration using LangGraph.
- Develop scalable cloud-based data pipelines.
- Deploy containerized services to the cloud (Render).
- Integrate with a paper-trading execution platform (Alpaca).
- Implement financial backtesting infrastructure.
- Integrate Claude into real-world workflows.
- Gain experience with modern AI-engineering patterns.

### Product goals

- Generate AI-powered investment research.
- Produce paper-trading recommendations.
- Simulate equity and options trading.
- Evaluate existing portfolio holdings.
- Evaluate portfolio performance over time.
- Compare performance against market benchmarks.
- Provide explainable reasoning behind every recommendation.

## Key design decisions

These decisions were made during planning and the rest of the docs assume them:

1. **Execution via Alpaca paper trading, not a custom engine.** The original concept floated a custom paper-trading engine. We instead integrate Alpaca's free paper-trading API for realistic simulated fills, position tracking, and portfolio sync. This keeps the project focused on its differentiator — multi-agent research — while still demonstrating brokerage-API integration. A custom fill simulator is listed as an optional later enhancement. See `docs/06-data-sources.md`.
2. **MVP-first, phased build.** The full vision (7 agents, options, cloud deploy, backtesting, ML) is the destination, not the first deliverable. The roadmap in `docs/07-roadmap.md` defines a shippable core first and layers ambition on top.
3. **Explainability is non-negotiable.** Every recommendation carries per-agent votes and a reasoning report.

## What to read next

- `01-product-spec.md` — features, recommendation types, UI.
- `02-architecture.md` — how the pieces fit together.
- `03-agents.md` — the heart of the system.
- `07-roadmap.md` — what to build, in order.

# 08 — Coding Standards & Conventions

Keep the codebase boring and consistent so the agent system can stay the interesting part.

## Python (backend)

- **Version:** 3.12. Type hints everywhere; `mypy` clean.
- **Style:** `ruff` for lint + format (config in `backend/pyproject.toml`). 100-col lines. snake_case for functions/vars, PascalCase for classes.
- **Framework:** async FastAPI handlers. Handlers stay thin — validate, delegate to a service/agent, map to a response schema. No business logic in routes.
- **Schemas vs models:** Pydantic v2 models in `app/schemas/` for I/O; SQLAlchemy ORM in `app/models/`. Never return ORM objects directly from an endpoint.
- **Config:** all settings via `pydantic-settings` in `app/core/config.py`, sourced from env. No `os.getenv` scattered around. No secrets in code.
- **Errors:** raise `HTTPException` with correct status codes; let FastAPI render `{detail}`. Catch vendor SDK errors at the adapter boundary and translate them.
- **Money:** use `Decimal`/`numeric`, never float, for prices/quantities/cash.
- **Determinism:** scoring (`aggregate_votes`) and backtests are pure and seeded. The LLM generates prose, not the numbers that must reproduce.

## TypeScript / React (frontend)

- **Strict mode** on. No `any` without a written reason.
- Functional components + hooks only. Data-fetching in `src/hooks/`, API calls in `src/api/`, shared types in `src/types/`.
- Import alias `@/` → `src/` (configured in `tsconfig.json` + `vite.config.ts`).
- Tailwind utility classes for styling; component files PascalCase (`ResearchTab.tsx`).
- Charts via Recharts. Always handle loading and error states (agent runs are slow).

## Project layout rules

- Backend domain code under `app/`; one agent per file in `app/agents/`; one provider adapter per file under `app/services/data_sources/` and `app/services/execution/`.
- Agents depend on `services.*` interfaces, never on a vendor SDK directly.
- Keep `docs/` authoritative: if you change a schema, an agent contract, or an endpoint, update the matching doc in the same change.

## Testing

- `pytest` in `backend/tests/`. Unit-test all indicator math, `aggregate_votes`, and backtest metrics with fixed-input fixtures and known expected outputs.
- Mock external providers at the adapter interface — no live API calls in unit tests.
- Add at least one integration test per phase exercising the phase's end-to-end slice.
- Frontend: type-check (`npm run typecheck`) must pass; add component tests for non-trivial UI as it grows.

## Git & CI

- Small, vertical PRs. Conventional-commit-style messages (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- CI (`.github/workflows/ci.yml`) runs ruff, pytest, and frontend typecheck on every PR; keep it green.
- Tag a release at the end of each roadmap phase so there's always a working demo.

## Security & safety

- **Paper trading only.** The execution service must refuse to run against any Alpaca base URL other than the paper host.
- Secrets only via env / secret manager; `.env` is gitignored; keep `.env.example` current.
- Validate and sanitize all user input at the schema layer.
- Surface the "research / not financial advice" disclaimer in both UI and recommendation responses.

## LLM usage (Claude)

- Centralize Claude calls in one client wrapper (`app/core/llm.py` or `app/services/llm.py`); model name from config.
- Give each agent a focused system prompt and require **structured output** (parse into the agent's Pydantic schema). Validate; retry once on parse failure; abstain on repeated failure.
- Keep prompts in code/constants, not scattered string literals, so they can be versioned and tuned.
- Never let the model invent numeric facts — feed it data from the adapters and have it reason over that.

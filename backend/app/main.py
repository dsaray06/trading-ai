"""FastAPI entrypoint.

Phase 1: health check + the Research vertical slice (POST /research/{ticker}).
Auth, portfolio, and backtesting routers arrive in later phases (docs/07-roadmap.md).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import alpaca, auth, backtest, config, portfolio, research
from app.core.config import get_settings
from app.core.llm import get_llm_client
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Trading AI backend starting (env=%s)", settings.app_env)
    llm = get_llm_client()
    if llm.enabled:
        logger.info("LLM reasoning ENABLED (model=%s)", settings.anthropic_model)
    else:
        logger.info("LLM reasoning DISABLED — using templated fallback "
                    "(set ANTHROPIC_API_KEY to enable Claude)")
    yield


app = FastAPI(title="Trading AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(config.router)
app.include_router(auth.router)
app.include_router(alpaca.router)
app.include_router(research.router)
app.include_router(portfolio.router)
app.include_router(backtest.router)

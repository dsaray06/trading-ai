"""Research routes (docs/05-api-spec.md).

Handlers stay thin: validate input, delegate to the research service, map errors
to HTTP status codes. Phase 1 implements POST /research/{ticker}.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import OptionalUser
from app.db.session import get_db
from app.schemas.research import RecommendationResponse, ResearchRequest
from app.services.research import ResearchError, run_research

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/{ticker}", response_model=RecommendationResponse)
def research_ticker(
    ticker: str,
    db: Annotated[Session, Depends(get_db)],
    user: OptionalUser,
    request: ResearchRequest | None = None,
) -> RecommendationResponse:
    """Run the agent pipeline for a ticker and return an explained recommendation.

    Auth is optional: when a valid JWT is present, the logged-in user's own Alpaca
    keys are used to fetch the option chain (works from cloud IPs).
    """
    try:
        return run_research(db, ticker, request or ResearchRequest(), user=user)
    except ResearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

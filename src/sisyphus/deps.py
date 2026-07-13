"""Injeção de dependências — expõe o ThinkerService montado no lifespan."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from .config import settings
from .repositories.quotes import DailyQuoteRepository, SQLiteQuoteRepository
from .services.thinker_service import ThinkerService


def get_service(request: Request) -> ThinkerService:
    return request.app.state.service  # type: ignore[no-any-return]


Service = Annotated[ThinkerService, Depends(get_service)]


def get_daily_quote_repository() -> DailyQuoteRepository:
    return SQLiteQuoteRepository(settings.serving_db_path)


DailyQuotes = Annotated[DailyQuoteRepository, Depends(get_daily_quote_repository)]

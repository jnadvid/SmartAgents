"""Endpoints de métricas (Fase 2): datos agregados para el dashboard."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MetricsSummary
from app.security.auth import api_key_auth
from app.services import metrics_service

router = APIRouter(prefix="/metrics", tags=["metrics"], dependencies=[Depends(api_key_auth)])


@router.get("/summary", response_model=MetricsSummary)
def metrics_summary(db: Session = Depends(get_db)) -> MetricsSummary:
    return MetricsSummary(**metrics_service.build_summary(db))

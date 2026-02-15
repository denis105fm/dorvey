"""Cron endpoints - auto-rollback, auto-switch offers, etc. Call via external cron or Celery Beat."""

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.services.cron_runner import (
    run_auto_rollback,
    run_auto_pause_unprofitable,
    run_auto_switch_offers,
    run_pause_on_affiliate_issues,
    run_all,
)

router = APIRouter()


@router.post("/auto-rollback")
async def auto_rollback(
    threshold_percent: float = Query(15, ge=5, le=50),
    min_days: int = Query(7, ge=3, le=30),
    db=Depends(get_db),
):
    """Check doorways for CR drop and rollback. Call daily via cron."""
    r = await run_auto_rollback(db, threshold_percent, min_days)
    return {"status": "ok", **r}


@router.post("/auto-pause-unprofitable")
async def auto_pause_unprofitable(
    min_revenue: float = Query(0),
    min_days: int = Query(14, ge=7),
    db=Depends(get_db),
):
    """Pause doorways with negative ROI."""
    r = await run_auto_pause_unprofitable(db, min_revenue, min_days)
    return {"status": "ok", **r}


@router.post("/auto-switch-offers")
async def auto_switch_offers_on_cr_drop(
    threshold_percent: float = Query(15, ge=5, le=50),
    min_days: int = Query(7, ge=3, le=30),
    db=Depends(get_db),
):
    """When campaign CR drops and has 2+ offers, rotate priorities."""
    r = await run_auto_switch_offers(db, threshold_percent, min_days)
    return {"status": "ok", **r}


@router.post("/pause-on-affiliate-issues")
async def pause_on_affiliate_issues(
    min_conversions_drop_percent: float = Query(50, ge=20, le=90),
    min_days: int = Query(7, ge=3),
    db=Depends(get_db),
):
    """Pause doorways when campaign's affiliate shows conversion drop."""
    r = await run_pause_on_affiliate_issues(db, min_conversions_drop_percent, min_days)
    return {"status": "ok", **r}


@router.post("/run-all")
async def cron_run_all(db=Depends(get_db)):
    """
    Run all daily cron tasks: auto-rollback, auto-pause, auto-switch-offers, pause-on-affiliate.
    Один вызов вместо четырёх. Для cron: curl -X POST https://app/api/cron/run-all
    """
    return await run_all(db)

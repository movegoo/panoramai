"""
VGEO (Video GEO) Router.
Endpoints for Video Generative Engine Optimization analysis.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db, VgeoReport, Advertiser, Competitor, AdvertiserCompetitor
from core.auth import get_current_user
from core.permissions import verify_advertiser_access

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_advertiser_id(request: Request) -> int:
    """Extract advertiser ID from X-Advertiser-Id header."""
    adv_id = request.headers.get("X-Advertiser-Id")
    if not adv_id:
        raise HTTPException(status_code=400, detail="X-Advertiser-Id header required")
    try:
        return int(adv_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Advertiser-Id")


@router.post("/analyze")
async def analyze_vgeo(
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Launch a full VGEO analysis (async, can take 30-60s)."""
    adv_id = _get_advertiser_id(request)
    verify_advertiser_access(db, adv_id, user)

    from services.vgeo_analyzer import vgeo_analyzer

    try:
        result = await vgeo_analyzer.analyze(adv_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"VGEO analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse VGEO: {str(e)}")

    # Save report to DB
    report = VgeoReport(
        advertiser_id=adv_id,
        score_total=result["score"]["total"],
        score_alignment=result["score"]["alignment"],
        score_freshness=result["score"]["freshness"],
        score_presence=result["score"]["presence"],
        score_competitivity=result["score"]["competitivity"],
        report_data=result,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "report_id": report.id,
        **result,
    }


@router.get("/report")
async def get_vgeo_report(
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the latest VGEO report for the current advertiser."""
    adv_id = _get_advertiser_id(request)
    verify_advertiser_access(db, adv_id, user)

    report = (
        db.query(VgeoReport)
        .filter(VgeoReport.advertiser_id == adv_id)
        .order_by(VgeoReport.created_at.desc())
        .first()
    )

    if not report:
        return {
            "has_report": False,
            "score": None,
            "report_data": None,
            "created_at": None,
        }

    return {
        "has_report": True,
        "report_id": report.id,
        "score": {
            "total": report.score_total,
            "alignment": report.score_alignment,
            "freshness": report.score_freshness,
            "presence": report.score_presence,
            "competitivity": report.score_competitivity,
        },
        "created_at": report.created_at.isoformat() if report.created_at else None,
        **(report.report_data or {}),
    }


@router.get("/comparison")
async def get_vgeo_comparison(
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get competitor comparison from the latest VGEO report."""
    adv_id = _get_advertiser_id(request)
    verify_advertiser_access(db, adv_id, user)

    report = (
        db.query(VgeoReport)
        .filter(VgeoReport.advertiser_id == adv_id)
        .order_by(VgeoReport.created_at.desc())
        .first()
    )

    if not report or not report.report_data:
        return {
            "has_data": False,
            "brand_score": None,
            "competitors": [],
        }

    data = report.report_data
    return {
        "has_data": True,
        "brand_score": data.get("score", {}),
        "competitors": data.get("competitors", []),
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }

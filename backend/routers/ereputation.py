"""
E-Reputation router.
Dashboard, competitor detail, comments explorer, alerts, and manual audit trigger.
"""
import json
import asyncio
from fastapi import APIRouter, Depends, Header, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional

from database import get_db, User, EReputationAudit, EReputationComment, Competitor
from core.auth import get_current_user
from core.permissions import (
    get_user_competitor_ids,
    get_user_competitors,
    parse_advertiser_header,
    verify_competitor_access,
)

router = APIRouter()


def _safe_json(text: Optional[str], default=None):
    """Parse JSON text safely, returning default on failure."""
    if not text:
        return default if default is not None else {}
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def _serialize_audit(audit: EReputationAudit) -> dict:
    """Serialize an audit to dict."""
    return {
        "id": audit.id,
        "competitor_id": audit.competitor_id,
        "reputation_score": audit.reputation_score,
        "nps": audit.nps,
        "sav_rate": audit.sav_rate,
        "financial_risk_rate": audit.financial_risk_rate,
        "engagement_rate": audit.engagement_rate,
        "earned_ratio": audit.earned_ratio,
        "sentiment_breakdown": _safe_json(audit.sentiment_breakdown, {"positive": 0, "negative": 0, "neutral": 0}),
        "platform_breakdown": _safe_json(audit.platform_breakdown, {}),
        "ai_synthesis": _safe_json(audit.ai_synthesis, {"insights": [], "recommendations": []}),
        "total_comments": audit.total_comments,
        "created_at": audit.created_at.isoformat() if audit.created_at else None,
    }


def _serialize_comment(c: EReputationComment) -> dict:
    """Serialize a comment to dict."""
    return {
        "id": c.id,
        "audit_id": c.audit_id,
        "competitor_id": c.competitor_id,
        "platform": c.platform,
        "comment_id": c.comment_id,
        "source_type": c.source_type,
        "source_url": c.source_url,
        "source_title": c.source_title,
        "author": c.author,
        "text": c.text,
        "likes": c.likes,
        "replies": c.replies,
        "published_at": c.published_at.isoformat() if c.published_at else None,
        "collected_at": c.collected_at.isoformat() if c.collected_at else None,
        "sentiment": c.sentiment,
        "sentiment_score": c.sentiment_score,
        "categories": _safe_json(c.categories, []),
        "is_alert": c.is_alert,
        "alert_reason": c.alert_reason,
    }


@router.get("/dashboard")
async def ereputation_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Get latest e-reputation audit per competitor."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp_ids = get_user_competitor_ids(db, user, advertiser_id=adv_id)

    if not comp_ids:
        return {"competitors": [], "summary": {}}

    # Get latest audit per competitor
    results = []
    for comp_id in comp_ids:
        audit = (
            db.query(EReputationAudit)
            .filter(EReputationAudit.competitor_id == comp_id)
            .order_by(desc(EReputationAudit.created_at))
            .first()
        )
        comp = db.query(Competitor).filter(Competitor.id == comp_id).first()
        if comp:
            entry = {
                "competitor_id": comp.id,
                "competitor_name": comp.name,
                "logo_url": comp.logo_url,
                "audit": _serialize_audit(audit) if audit else None,
            }
            results.append(entry)

    # Summary stats
    audited = [r for r in results if r["audit"]]
    avg_score = sum(r["audit"]["reputation_score"] for r in audited) / len(audited) if audited else 0
    avg_nps = sum(r["audit"]["nps"] for r in audited) / len(audited) if audited else 0
    total_alerts = 0
    for r in audited:
        comp_id = r["competitor_id"]
        total_alerts += db.query(EReputationComment).filter(
            EReputationComment.competitor_id == comp_id,
            EReputationComment.is_alert == True,
        ).count()

    return {
        "competitors": results,
        "summary": {
            "avg_reputation_score": round(avg_score, 1),
            "avg_nps": round(avg_nps, 1),
            "total_audited": len(audited),
            "total_alerts": total_alerts,
        },
    }


@router.get("/competitor/{competitor_id}")
async def ereputation_competitor_detail(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Get detailed e-reputation data for a specific competitor."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp_ids = get_user_competitor_ids(db, user, advertiser_id=adv_id)
    if competitor_id not in comp_ids:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")

    audit = (
        db.query(EReputationAudit)
        .filter(EReputationAudit.competitor_id == competitor_id)
        .order_by(desc(EReputationAudit.created_at))
        .first()
    )

    if not audit:
        return {"audit": None, "comments": [], "alerts": []}

    comments = (
        db.query(EReputationComment)
        .filter(EReputationComment.audit_id == audit.id)
        .order_by(desc(EReputationComment.likes))
        .limit(200)
        .all()
    )

    alerts = [c for c in comments if c.is_alert]

    return {
        "audit": _serialize_audit(audit),
        "comments": [_serialize_comment(c) for c in comments],
        "alerts": [_serialize_comment(c) for c in alerts],
    }


@router.get("/comments")
async def ereputation_comments(
    competitor_id: Optional[int] = None,
    platform: Optional[str] = None,
    sentiment: Optional[str] = None,
    source_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Paginated comment explorer with filters."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp_ids = get_user_competitor_ids(db, user, advertiser_id=adv_id)

    query = db.query(EReputationComment).filter(
        EReputationComment.competitor_id.in_(comp_ids)
    )

    if competitor_id:
        if competitor_id not in comp_ids:
            raise HTTPException(status_code=404, detail="Concurrent non trouvé")
        query = query.filter(EReputationComment.competitor_id == competitor_id)
    if platform:
        query = query.filter(EReputationComment.platform == platform)
    if sentiment:
        query = query.filter(EReputationComment.sentiment == sentiment)
    if source_type:
        query = query.filter(EReputationComment.source_type == source_type)

    total = query.count()
    comments = (
        query.order_by(desc(EReputationComment.collected_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "comments": [_serialize_comment(c) for c in comments],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/alerts")
async def ereputation_alerts(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Get alert comments requiring attention."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp_ids = get_user_competitor_ids(db, user, advertiser_id=adv_id)

    alerts = (
        db.query(EReputationComment)
        .filter(
            EReputationComment.competitor_id.in_(comp_ids),
            EReputationComment.is_alert == True,
        )
        .order_by(desc(EReputationComment.collected_at))
        .limit(limit)
        .all()
    )

    return {
        "alerts": [_serialize_comment(c) for c in alerts],
        "total": len(alerts),
    }


@router.post("/run-audit")
async def run_ereputation_audit(
    competitor_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Run e-reputation audit manually. If competitor_id given, audit only that one."""
    from services.ereputation_service import ereputation_service

    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)

    if competitor_id:
        competitors = [c for c in competitors if c.id == competitor_id]
        if not competitors:
            raise HTTPException(status_code=404, detail="Concurrent non trouvé")

    async def _run():
        for comp in competitors[:10]:
            try:
                await ereputation_service.run_audit(comp, db)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Audit error for {comp.name}: {e}")
            await asyncio.sleep(2)

    asyncio.create_task(_run())

    return {
        "message": f"Audit e-réputation lancé pour {len(competitors[:10])} concurrent(s)",
        "competitors": [c.name for c in competitors[:10]],
    }

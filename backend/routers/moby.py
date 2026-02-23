"""Moby AI chatbot endpoints."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, SystemSetting, User
from core.auth import get_current_user
from services.moby_ai import moby_service

router = APIRouter()


class MobyMessage(BaseModel):
    role: str
    content: str


class MobyAskRequest(BaseModel):
    question: str
    history: list[MobyMessage] = []


class MobyAskResponse(BaseModel):
    answer: str
    sql: str | None = None
    row_count: int = 0
    error: str | None = None


class MobyConfigResponse(BaseModel):
    enabled: bool = True
    position: str = "bottom-right"


@router.post("/ask", response_model=MobyAskResponse)
async def moby_ask(
    data: MobyAskRequest,
    user: User = Depends(get_current_user),
):
    """Pose une question en langage naturel à Moby."""
    history = [{"role": m.role, "content": m.content} for m in data.history]
    result = await moby_service.process_question(data.question, history)
    return result


@router.get("/config", response_model=MobyConfigResponse)
async def moby_config(db: Session = Depends(get_db)):
    """Configuration du chatbot Moby."""
    enabled = True
    position = "bottom-right"

    row = db.query(SystemSetting).filter(SystemSetting.key == "moby_enabled").first()
    if row:
        enabled = row.value.lower() == "true"

    row = db.query(SystemSetting).filter(SystemSetting.key == "moby_position").first()
    if row and row.value in ("bottom-right", "bottom-left", "top-right", "top-left"):
        position = row.value

    return {"enabled": enabled, "position": position}

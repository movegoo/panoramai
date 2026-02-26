"""
Smart Filter Router.
Generic endpoint for AI-powered natural language filtering across all pages.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from services.smart_filter import smart_filter_service, PAGE_PROMPTS

router = APIRouter()


class SmartFilterRequest(BaseModel):
    query: str
    page: str = "ads"


@router.post("")
async def smart_filter(req: SmartFilterRequest):
    """Translate a natural language query into structured filters using AI.

    Accepts a `page` parameter to select the right filter schema:
    ads, social, apps, geo, seo, signals, tendances, overview, geo-tracking, vgeo
    """
    page = req.page if req.page in PAGE_PROMPTS else "ads"
    result = await smart_filter_service.parse_query(req.query, page=page)
    return result

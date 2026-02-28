"""
Market data API router.
Endpoints for accessing French government open data from data.gouv.fr.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from database import User
from core.auth import get_admin_user
from services.datagouv import datagouv_service

router = APIRouter()


# =============================================================================
# Dataset Information
# =============================================================================

@router.get("/datasets")
async def list_available_datasets():
    """List all available datasets from data.gouv.fr."""
    return {
        "datasets": datagouv_service.get_available_datasets(),
        "source": "data.gouv.fr",
        "description": "French government open data for market intelligence"
    }


@router.get("/summary")
async def get_market_summary():
    """Get a summary of available market data."""
    datasets = datagouv_service.get_available_datasets()

    return {
        "available_datasets": len(datasets),
        "datasets": datasets,
        "data_sources": [
            {
                "name": "data.gouv.fr",
                "description": "Plateforme ouverte des données publiques françaises",
                "url": "https://www.data.gouv.fr"
            },
            {
                "name": "INSEE",
                "description": "Institut national de la statistique et des études économiques",
                "url": "https://www.insee.fr"
            }
        ],
        "coverage": {
            "geographic": "France",
            "sectors": ["Retail", "Commerce", "Consumption"]
        }
    }


# =============================================================================
# Store Locations (BANCO)
# =============================================================================

@router.get("/stores")
async def get_stores(
    city: Optional[str] = Query(None, description="Filter by city name"),
    postal_code: Optional[str] = Query(None, description="Filter by postal code prefix"),
    department: Optional[str] = Query(None, description="Filter by department code"),
    category: Optional[str] = Query(None, description="Filter by store category"),
    limit: int = Query(100, ge=1, le=1000, description="Max results")
):
    """
    Get store locations from BANCO database.

    Filters stores by location and category.
    """
    try:
        return await datagouv_service.get_stores_by_location(
            city=city,
            postal_code=postal_code,
            department=department,
            category=category,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stores/categories")
async def get_store_categories():
    """Get list of available store categories (NAF codes)."""
    return {
        "categories": [
            {"code": "4711", "name": "Commerce de détail en magasin non spécialisé à prédominance alimentaire"},
            {"code": "4719", "name": "Autre commerce de détail en magasin non spécialisé"},
            {"code": "4721", "name": "Commerce de détail de fruits et légumes"},
            {"code": "4722", "name": "Commerce de détail de viandes et produits à base de viande"},
            {"code": "4723", "name": "Commerce de détail de poissons, crustacés et mollusques"},
            {"code": "4724", "name": "Commerce de détail de pain, pâtisserie et confiserie"},
            {"code": "4725", "name": "Commerce de détail de boissons"},
            {"code": "4726", "name": "Commerce de détail de produits à base de tabac"},
            {"code": "4729", "name": "Autres commerces de détail alimentaires en magasin spécialisé"},
            {"code": "4751", "name": "Commerce de détail de textiles"},
            {"code": "4771", "name": "Commerce de détail d'habillement"},
            {"code": "4772", "name": "Commerce de détail de chaussures et articles en cuir"},
            {"code": "4773", "name": "Commerce de détail de produits pharmaceutiques"},
            {"code": "4775", "name": "Commerce de détail de parfumerie et de produits de beauté"},
            {"code": "4791", "name": "Vente à distance"}
        ],
        "source": "NAF Rev. 2 - INSEE"
    }


# =============================================================================
# Market Trends
# =============================================================================

@router.get("/trends")
async def get_market_trends(
    sector: Optional[str] = Query(None, description="Filter by sector"),
    period: str = Query("monthly", description="Data period: monthly, quarterly, yearly")
):
    """
    Get market activity indicators.

    Returns economic indicators for retail and commerce sectors.
    """
    try:
        return await datagouv_service.get_market_trends(sector=sector, period=period)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends/sectors")
async def get_available_sectors():
    """Get list of available sectors for trend analysis."""
    return {
        "sectors": [
            {"code": "retail", "name": "Commerce de détail"},
            {"code": "food", "name": "Commerce alimentaire"},
            {"code": "textile", "name": "Textile et habillement"},
            {"code": "household", "name": "Équipement du foyer"},
            {"code": "health", "name": "Santé et beauté"},
            {"code": "digital", "name": "Commerce en ligne"}
        ]
    }


# =============================================================================
# Consumption Data
# =============================================================================

@router.get("/consumption")
async def get_consumption_data(
    category: Optional[str] = Query(None, description="Filter by consumption category"),
    year: Optional[int] = Query(None, description="Filter by year")
):
    """
    Get household consumption data.

    Returns spending patterns by product category (COICOP classification).
    """
    try:
        return await datagouv_service.get_consumption_data(category=category, year=year)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consumption/categories")
async def get_consumption_categories():
    """Get list of consumption categories (COICOP classification)."""
    return {
        "categories": [
            {"code": "01", "name": "Produits alimentaires et boissons non alcoolisées"},
            {"code": "02", "name": "Boissons alcoolisées et tabac"},
            {"code": "03", "name": "Articles d'habillement et chaussures"},
            {"code": "04", "name": "Logement, eau, gaz, électricité"},
            {"code": "05", "name": "Meubles, articles de ménage"},
            {"code": "06", "name": "Santé"},
            {"code": "07", "name": "Transports"},
            {"code": "08", "name": "Communications"},
            {"code": "09", "name": "Loisirs et culture"},
            {"code": "10", "name": "Enseignement"},
            {"code": "11", "name": "Restaurants et hôtels"},
            {"code": "12", "name": "Biens et services divers"}
        ],
        "source": "COICOP - Classification of Individual Consumption According to Purpose"
    }


# =============================================================================
# Data Refresh
# =============================================================================

@router.post("/refresh")
async def refresh_market_data(user: User = Depends(get_admin_user)):
    """Refresh all cached market data from data.gouv.fr."""
    try:
        await datagouv_service.refresh_all()
        return {
            "message": "Market data refresh completed",
            "datasets_refreshed": [d["key"] for d in datagouv_service.get_available_datasets()]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

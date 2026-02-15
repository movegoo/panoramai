"""
Authentication router.
Register, login, and user profile endpoints.
"""
import traceback
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, User, Advertiser
from core.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


def _build_user_dict(user: User, db: Session) -> dict:
    """Build user response dict."""
    advertisers = db.query(Advertiser).filter(
        Advertiser.user_id == user.id, Advertiser.is_active == True
    ).order_by(Advertiser.id).all()

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "has_brand": len(advertisers) > 0,
        "is_admin": bool(user.is_admin) if user.is_admin is not None else False,
        "advertisers": [
            {"id": a.id, "company_name": a.company_name, "sector": a.sector, "logo_url": a.logo_url}
            for a in advertisers
        ],
    }


@router.post("/register")
async def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new user account."""
    try:
        if len(data.password) < 6:
            raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 6 caractères")

        existing = db.query(User).filter(User.email == data.email.lower().strip()).first()
        if existing:
            raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")

        user = User(
            email=data.email.lower().strip(),
            name=data.name or data.email.split("@")[0],
            password_hash=hash_password(data.password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(user.id)
        user_dict = _build_user_dict(user, db)

        return JSONResponse(content={"token": token, "user": user_dict})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import logging
        logging.getLogger(__name__).error(f"Registration error: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={
            "detail": "Une erreur est survenue lors de l'inscription",
        })


@router.post("/login")
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password."""
    try:
        user = db.query(User).filter(
            User.email == data.email.lower().strip(), User.is_active == True
        ).first()

        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

        token = create_access_token(user.id)
        user_dict = _build_user_dict(user, db)

        return JSONResponse(content={"token": token, "user": user_dict})
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Login error: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={
            "detail": "Une erreur est survenue lors de la connexion",
        })


@router.delete("/reset-user")
async def reset_user(email: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Delete a user by email. Admin only."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")
    target = db.query(User).filter(User.email == email.lower().strip()).first()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    db.delete(target)
    db.commit()
    return {"message": f"User {email} deleted"}


@router.get("/me")
async def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user profile."""
    advertisers = db.query(Advertiser).filter(
        Advertiser.user_id == user.id, Advertiser.is_active == True
    ).order_by(Advertiser.id).all()

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "has_brand": len(advertisers) > 0,
        "brand_name": advertisers[0].company_name if advertisers else None,
        "is_admin": bool(user.is_admin) if user.is_admin is not None else False,
        "advertisers": [
            {"id": a.id, "company_name": a.company_name, "sector": a.sector, "logo_url": a.logo_url}
            for a in advertisers
        ],
    }

"""
Authentication router.
Register, login, and user profile endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

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


class AuthResponse(BaseModel):
    token: str
    user: dict


@router.post("/register", response_model=AuthResponse)
async def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new user account."""
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
    has_brand = db.query(Advertiser).filter(
        Advertiser.user_id == user.id, Advertiser.is_active == True
    ).first() is not None

    return AuthResponse(
        token=token,
        user={"id": user.id, "email": user.email, "name": user.name, "has_brand": has_brand},
    )


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password."""
    user = db.query(User).filter(
        User.email == data.email.lower().strip(), User.is_active == True
    ).first()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    token = create_access_token(user.id)
    has_brand = db.query(Advertiser).filter(
        Advertiser.user_id == user.id, Advertiser.is_active == True
    ).first() is not None

    return AuthResponse(
        token=token,
        user={"id": user.id, "email": user.email, "name": user.name, "has_brand": has_brand},
    )


@router.get("/me")
async def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user profile."""
    brand = db.query(Advertiser).filter(
        Advertiser.user_id == user.id, Advertiser.is_active == True
    ).first()

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "has_brand": brand is not None,
        "brand_name": brand.company_name if brand else None,
    }

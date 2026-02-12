"""
Authentication utilities.
JWT token management and password hashing.
"""
import bcrypt
import jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.config import settings
from database import get_db, User

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=settings.JWT_EXPIRATION_DAYS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: extract and validate user from Bearer token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentification requise")

    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token invalide")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur non trouvé")

    return user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency: require admin privileges."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    """Like get_current_user but returns None instead of 401 if no token."""
    if not credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None


def claim_orphans(db: Session, user: User) -> None:
    """Assign orphan brand & competitors to this user.

    Claims records with user_id=NULL.
    Also reclaims competitors held by users who don't own any brand,
    so that they go to an actual brand owner instead.
    """
    from database import Advertiser, Competitor
    from sqlalchemy import and_

    # 1. Claim orphan brands (user_id=NULL)
    db.query(Advertiser).filter(
        Advertiser.is_active == True,
        Advertiser.user_id == None,
    ).update({"user_id": user.id})

    # 2. Claim orphan competitors (user_id=NULL)
    db.query(Competitor).filter(
        Competitor.is_active == True,
        Competitor.user_id == None,
    ).update({"user_id": user.id})

    db.flush()

    # 3. If this user has a brand, reclaim competitors stuck on users without brands
    has_brand = db.query(Advertiser).filter(
        Advertiser.user_id == user.id,
        Advertiser.is_active == True,
    ).first()

    if has_brand:
        # IDs of users who own an active brand (other than current user)
        other_brand_owners = {
            row[0] for row in
            db.query(Advertiser.user_id).filter(
                Advertiser.is_active == True,
                Advertiser.user_id != None,
                Advertiser.user_id != user.id,
            ).all()
        }

        # Reclaim competitors from non-brand-owners
        stray = db.query(Competitor).filter(
            Competitor.is_active == True,
            Competitor.user_id != user.id,
            Competitor.user_id != None,
        )
        if other_brand_owners:
            stray = stray.filter(~Competitor.user_id.in_(other_brand_owners))
        stray.update({"user_id": user.id}, synchronize_session=False)

    db.commit()

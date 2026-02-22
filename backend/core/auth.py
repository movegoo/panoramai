"""
Authentication utilities.
JWT token management and password hashing.
"""
import bcrypt
import jwt
from datetime import datetime, timedelta
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.config import settings
from database import get_db, User, Advertiser, UserAdvertiser

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


def get_current_advertiser(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_advertiser_id: str | None = Header(None),
) -> Advertiser:
    """Resolve the active advertiser via user_advertisers join table."""
    # Get all advertiser IDs this user has access to
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(
        UserAdvertiser.user_id == user.id
    ).all()]

    if not user_adv_ids:
        raise HTTPException(status_code=404, detail="Aucune enseigne configurée")

    if x_advertiser_id:
        try:
            adv_id = int(x_advertiser_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="X-Advertiser-Id invalide")
        if adv_id not in user_adv_ids:
            raise HTTPException(status_code=403, detail="Accès refusé à cet annonceur")
        advertiser = db.query(Advertiser).filter(
            Advertiser.id == adv_id,
            Advertiser.is_active == True,
        ).first()
        if not advertiser:
            raise HTTPException(status_code=404, detail="Enseigne non trouvée")
        return advertiser

    # Fallback: first advertiser
    advertiser = db.query(Advertiser).filter(
        Advertiser.id.in_(user_adv_ids),
        Advertiser.is_active == True,
    ).order_by(Advertiser.id).first()
    if not advertiser:
        raise HTTPException(status_code=404, detail="Aucune enseigne configurée")
    return advertiser

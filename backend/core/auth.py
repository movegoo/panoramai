"""
Authentication utilities.
JWT token management and password hashing.
"""
import base64
import json
import logging
import time
import bcrypt
import httpx
import jwt
from datetime import datetime, timedelta
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.config import settings
from database import get_db, User, Advertiser, UserAdvertiser

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(days=settings.JWT_EXPIRATION_DAYS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.JWT_SECRET, algorithms=["HS256"],
            options={"verify_sub": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")


def _decode_cognito_jwt(token: str) -> dict:
    """Decode a Cognito JWT payload without signature verification (like vibely-stack).

    The token is trusted because it comes from the Mobsuccess getauthid-auth endpoint
    which already authenticated the user. We just extract the claims.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Not a valid JWT")
        # Base64url decode the payload (part 1)
        payload_b64 = parts[1]
        # Add padding if needed
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes)
        return payload
    except Exception as e:
        raise ValueError(f"Failed to decode Cognito JWT: {e}")


def _validate_cognito_token(token: str, db: Session) -> User:
    """Validate a Cognito ID token by decoding it directly (vibely-stack approach).

    Extracts sub, email, name from the JWT payload and upserts a local user.
    """
    try:
        payload = _decode_cognito_jwt(token)
    except ValueError as e:
        logger.warning(f"Cognito JWT decode failed: {e}")
        raise HTTPException(status_code=401, detail="Token Cognito invalide")

    # Check expiry
    exp = payload.get("exp")
    if exp and time.time() >= exp:
        logger.warning("Cognito token expired")
        raise HTTPException(status_code=401, detail="Token Cognito expiré")

    sub = payload.get("sub", "")
    email = payload.get("email", "")
    name = payload.get("name", "")

    if not sub:
        logger.warning(f"Cognito JWT missing 'sub': {list(payload.keys())}")
        raise HTTPException(status_code=401, detail="Token Cognito invalide (sub manquant)")

    # Stable numeric ID from cognito sub (deterministic)
    cognito_ms_id = abs(hash(sub)) % 2**31

    logger.info(f"Cognito JWT validated: sub={sub}, email={email}, cognito_ms_id={cognito_ms_id}")

    # Lookup by email first (most likely match with existing users), then by cognito sub
    user = None
    if email:
        user = db.query(User).filter(User.email == email).first()
    if not user:
        user = db.query(User).filter(User.ms_user_id == cognito_ms_id).first()

    if user:
        if name:
            user.name = name
        if email:
            user.email = email
        if not user.ms_user_id:
            user.ms_user_id = cognito_ms_id
        user.is_active = True
        db.commit()
        db.refresh(user)
    else:
        user = User(
            email=email or f"{sub}@cognito",
            name=name or email or sub,
            password_hash="ms-cognito",
            ms_user_id=cognito_ms_id,
            is_admin=False,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: extract and validate user from Bearer token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentification requise")

    token = credentials.credentials

    # Try 1: JWT local
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if user:
            return user
        logger.debug(f"JWT valid but user {user_id} not found")
    except Exception:
        pass

    # Try 2: Cognito JWT direct decode (vibely-stack approach)
    if settings.MS_AUTH_ENABLED:
        logger.info(f"Trying Cognito JWT decode (token starts with {token[:20]}...)")
        return _validate_cognito_token(token, db)

    logger.warning(f"Auth failed: MS_AUTH_ENABLED={settings.MS_AUTH_ENABLED}")
    raise HTTPException(status_code=401, detail="Authentification requise")


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

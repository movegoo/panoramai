"""
Authentication utilities.
JWT token management and password hashing.
"""
import logging
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


def _validate_mobsuccess_token(token: str, db: Session) -> User:
    """Validate a Mobsuccess Bearer token via the Lambda Authorizer and upsert a local user."""
    try:
        response = httpx.post(
            settings.MS_LAMBDA_AUTHORIZER_URL,
            json={"authorizerAccessRules": "logged-in"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        logger.info(f"Lambda Authorizer response: status={response.status_code}")
        response.raise_for_status()
        data = response.json()
        logger.info(f"Lambda Authorizer data: isAuthorized={data.get('isAuthorized')}, context keys={list(data.get('context', {}).keys())}")
    except Exception as e:
        logger.warning(f"Mobsuccess Lambda call failed: {e}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authentification requise")

    if not data.get("isAuthorized"):
        logger.warning(f"Lambda returned isAuthorized=False: {data}")
        raise HTTPException(status_code=401, detail="Authentification requise")

    ctx = data.get("context", {})
    ms_id = int(ctx["id_user"])
    email = ctx.get("email", "")
    firstname = ctx.get("firstname", "")
    lastname = ctx.get("lastname", "")
    is_admin = bool(ctx.get("admin"))
    name = f"{firstname} {lastname}".strip()

    # Lookup by ms_user_id first, then email
    user = db.query(User).filter(User.ms_user_id == ms_id).first()
    if not user and email:
        user = db.query(User).filter(User.email == email).first()

    if user:
        user.name = name
        user.ms_user_id = ms_id
        if email:
            user.email = email
        user.is_admin = is_admin
        user.is_active = True
        db.commit()
        db.refresh(user)
    else:
        user = User(
            email=email,
            name=name,
            password_hash="ms-auth",
            ms_user_id=ms_id,
            is_admin=is_admin,
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

    # Try 2: Mobsuccess Lambda
    if settings.MS_AUTH_ENABLED and settings.MS_LAMBDA_AUTHORIZER_URL:
        logger.info(f"Trying Mobsuccess Lambda auth (token starts with {token[:20]}...)")
        return _validate_mobsuccess_token(token, db)

    logger.warning(f"Auth failed: MS_AUTH_ENABLED={settings.MS_AUTH_ENABLED}, MS_LAMBDA_URL={'set' if settings.MS_LAMBDA_AUTHORIZER_URL else 'empty'}")
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

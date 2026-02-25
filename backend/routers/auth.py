"""
Authentication router.
Register, login, and user profile endpoints.
"""
import traceback
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, User, Advertiser
from core.auth import hash_password, verify_password, create_access_token, get_current_user
from core.config import settings

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
    from database import UserAdvertiser
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    advertisers = db.query(Advertiser).filter(
        Advertiser.id.in_(user_adv_ids), Advertiser.is_active == True
    ).order_by(Advertiser.id).all() if user_adv_ids else []

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
    from database import UserAdvertiser
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
    advertisers = db.query(Advertiser).filter(
        Advertiser.id.in_(user_adv_ids), Advertiser.is_active == True
    ).order_by(Advertiser.id).all() if user_adv_ids else []

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


@router.post("/debug-lambda")
async def debug_lambda(authorization: str | None = Header(None)):
    """
    Debug: replay the exact Lambda Authorizer call and return full request + response + curl.
    Temporary endpoint for Mobsuccess devs to investigate. No auth required.
    """
    import httpx
    import json as json_mod
    import base64

    if not authorization:
        raise HTTPException(status_code=400, detail="Pass Authorization header with Bearer token")

    token = authorization.replace("Bearer ", "").strip()

    lambda_url = settings.MS_LAMBDA_AUTHORIZER_URL
    request_body = {"authorizerAccessRules": "logged-in"}

    curl_cmd = (
        f'curl -v -X POST "{lambda_url}" \\\n'
        f'  -H "Content-Type: application/json" \\\n'
        f'  -H "Authorization: Bearer {token}" \\\n'
        f"  -d '{json_mod.dumps(request_body)}'"
    )

    # Make the actual call
    response_data = None
    response_status = None
    error_msg = None
    try:
        response = httpx.post(
            lambda_url,
            json=request_body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        response_status = response.status_code
        response_data = response.json()
    except Exception as e:
        error_msg = str(e)

    # Decode JWT header + payload (no signature verification) for inspection
    jwt_header = None
    jwt_payload_preview = None
    jwt_parts = token.split(".")
    if len(jwt_parts) >= 2:
        try:
            padded = jwt_parts[0] + "=" * (4 - len(jwt_parts[0]) % 4)
            jwt_header = json_mod.loads(base64.urlsafe_b64decode(padded))
            padded2 = jwt_parts[1] + "=" * (4 - len(jwt_parts[1]) % 4)
            full_payload = json_mod.loads(base64.urlsafe_b64decode(padded2))
            # Only expose non-sensitive fields
            jwt_payload_preview = {
                k: v for k, v in full_payload.items()
                if k in ("iss", "aud", "token_use", "auth_time", "exp", "iat",
                         "sub", "cognito:username", "email", "custom:id_user",
                         "scope", "client_id")
            }
        except Exception:
            pass

    return {
        "config": {
            "ms_auth_enabled": settings.MS_AUTH_ENABLED,
            "lambda_url": lambda_url,
        },
        "request_sent_to_lambda": {
            "method": "POST",
            "url": lambda_url,
            "headers": {
                "Authorization": f"Bearer {token[:30]}...{token[-10:]}",
                "Content-Type": "application/json",
            },
            "body": request_body,
        },
        "lambda_response": {
            "status_code": response_status,
            "body": response_data,
            "error": error_msg,
        },
        "token_inspection": {
            "jwt_header": jwt_header,
            "jwt_payload_preview": jwt_payload_preview,
            "token_length": len(token),
        },
        "curl_equivalent": curl_cmd,
    }

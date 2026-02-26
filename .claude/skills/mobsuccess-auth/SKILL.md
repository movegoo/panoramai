---
name: mobsuccess-auth
description: Guide complet pour implementer l'authentification SSO Mobsuccess (Cognito) dans un projet vibe-code. Utilise ce skill quand l'utilisateur demande d'ajouter l'auth Mobsuccess, le SSO, ou la gestion multi-enseigne.
argument-hint: [action]
---

# Mobsuccess Auth SSO — Guide d'implementation

Guide de reference pour integrer l'authentification SSO Mobsuccess (Cognito) dans un projet web, teste et valide en production sur PanoramAI.

## Architecture

```
Utilisateur clique "Se connecter avec Mobsuccess"
    |
    v
Redirect vers MS_REMOTE_AUTH_URL (page login Mobsuccess)
    |
    v
Cognito Mobsuccess authentifie l'utilisateur
    |
    v
Redirect vers /login?userId=...&authId=...
    |
    v
Frontend appelle getauthid-auth (API Mobsuccess)
    |
    v
Recoit cognito_id_token (JWT)
    |
    v
Frontend stocke le token dans localStorage
    |
    v
Backend decode le JWT Cognito directement (sans Lambda Authorizer)
    |
    v
User cree/mis a jour en base locale
```

## Variables d'environnement

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_MS_REMOTE_AUTH_URL=https://app.mobsuccess.com/auth
NEXT_PUBLIC_MS_API_ENDPOINT=https://app.mobsuccess.com
```

### Backend (.env)

```env
JWT_SECRET=<secret-aleatoire-32-chars-min>
JWT_EXPIRATION_DAYS=7
MS_AUTH_ENABLED=true
```

## Backend (FastAPI)

### 1. Config (core/config.py)

```python
class Settings:
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    JWT_EXPIRATION_DAYS: int = int(os.getenv("JWT_EXPIRATION_DAYS", "7"))
    MS_AUTH_ENABLED: bool = os.getenv("MS_AUTH_ENABLED", "false").lower() == "true"
```

### 2. Modele User (database.py)

```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, default="")
    password_hash = Column(String, default="")  # "ms-cognito" pour les users SSO
    ms_user_id = Column(Integer, nullable=True)  # Hash deterministe du sub Cognito
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

class Advertiser(Base):
    __tablename__ = "advertisers"
    id = Column(Integer, primary_key=True)
    company_name = Column(String)
    sector = Column(String)

class UserAdvertiser(Base):
    __tablename__ = "user_advertisers"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    advertiser_id = Column(Integer, ForeignKey("advertisers.id"))
    role = Column(String, default="member")  # "owner", "admin", "member"
```

### 3. Auth (core/auth.py)

```python
import jwt
import base64
import json
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)

# --- JWT local ---

def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.JWT_EXPIRATION_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"], options={"verify_exp": True})

# --- Cognito JWT ---

def _decode_cognito_jwt(token: str) -> dict:
    """Decode un JWT Cognito sans verification de signature.
    Le token est de confiance car il vient de l'endpoint getauthid-auth."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Not a valid JWT")
    payload_b64 = parts[1]
    # Ajouter le padding base64
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding
    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    return json.loads(payload_bytes)

def _validate_cognito_token(token: str, db: Session) -> User:
    """Valide un JWT Cognito et upsert le user local."""
    payload = _decode_cognito_jwt(token)

    # Verifier expiration
    exp = payload.get("exp")
    if exp and datetime.now(timezone.utc).timestamp() > exp:
        raise HTTPException(status_code=401, detail="Token expire")

    sub = payload.get("sub")
    email = payload.get("email", "")
    name = payload.get("name", email.split("@")[0] if email else "User")

    if not sub:
        raise HTTPException(status_code=401, detail="JWT invalide (sub manquant)")

    # ID numerique deterministe depuis le sub Cognito
    cognito_ms_id = abs(hash(sub)) % 2**31

    # Lookup par email d'abord, puis par ms_user_id
    user = db.query(User).filter(User.email == email).first() if email else None
    if not user:
        user = db.query(User).filter(User.ms_user_id == cognito_ms_id).first()

    if user:
        # Mettre a jour les infos
        if email and user.email != email:
            user.email = email
        if name and user.name != name:
            user.name = name
        user.ms_user_id = cognito_ms_id
    else:
        # Creer un nouveau user
        user = User(
            email=email or f"{sub}@cognito",
            name=name,
            password_hash="ms-cognito",
            ms_user_id=cognito_ms_id,
            is_active=True,
            is_admin=False,
        )
        db.add(user)

    db.commit()
    db.refresh(user)
    return user

# --- Dependencies FastAPI ---

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: extraire et valider le user depuis le Bearer token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentification requise")

    token = credentials.credentials

    # Essai 1: JWT local (auth par mot de passe)
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if user:
            return user
    except Exception:
        pass

    # Essai 2: JWT Cognito (SSO Mobsuccess)
    if settings.MS_AUTH_ENABLED:
        return _validate_cognito_token(token, db)

    raise HTTPException(status_code=401, detail="Authentification requise")

def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    """Comme get_current_user mais retourne None si pas de token."""
    if not credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None

def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """Dependency: exiger les privileges admin."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Acces reserve aux administrateurs")
    return user
```

### 4. Routes Auth (routers/auth.py)

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter()

class RegisterRequest(BaseModel):
    email: str
    name: str | None = None
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/register")
async def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Mot de passe trop court")
    existing = db.query(User).filter(User.email == data.email.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email deja utilise")
    user = User(
        email=data.email.lower().strip(),
        name=data.name or data.email.split("@")[0],
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return {"token": token, "user": _build_user_dict(user, db)}

@router.post("/login")
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.email == data.email.lower().strip(), User.is_active == True
    ).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    token = create_access_token(user.id)
    return {"token": token, "user": _build_user_dict(user, db)}

@router.get("/me")
async def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _build_user_dict(user, db)

def _build_user_dict(user: User, db: Session) -> dict:
    advs = db.query(UserAdvertiser).filter(UserAdvertiser.user_id == user.id).all()
    advertisers = []
    for ua in advs:
        adv = db.query(Advertiser).filter(Advertiser.id == ua.advertiser_id).first()
        if adv:
            advertisers.append({
                "id": adv.id,
                "company_name": adv.company_name,
                "sector": adv.sector,
            })
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "is_admin": user.is_admin,
        "advertisers": advertisers,
    }
```

## Frontend (Next.js 14)

### 1. API Client (lib/api.ts)

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
const MS_API_ENDPOINT = (process.env.NEXT_PUBLIC_MS_API_ENDPOINT || "https://app.mobsuccess.com").trim();

// Token management
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("auth_token");
}

export function setToken(token: string) {
  localStorage.setItem("auth_token", token);
}

export function clearToken() {
  localStorage.removeItem("auth_token");
}

export function getCurrentAdvertiserId(): string | null {
  return localStorage.getItem("current_advertiser_id");
}

// Echange Mobsuccess auth -> Cognito token
export async function exchangeMobsuccessAuth(
  userId: string,
  authId: string
): Promise<string> {
  const url = `${MS_API_ENDPOINT}/webservices/rest/getauthid-auth?userId=${encodeURIComponent(userId)}&authId=${encodeURIComponent(authId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Mobsuccess auth failed: ${res.status}`);
  const data = await res.json();
  const token = data?.cognito_id_token;
  if (!token) throw new Error("Token Cognito manquant dans la reponse");
  return token;
}

// Fetch wrapper avec auth automatique
export async function apiFetch(path: string, options: RequestInit = {}) {
  const token = getToken();
  const advertiserId = getCurrentAdvertiserId();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (advertiserId) headers["X-Advertiser-Id"] = advertiserId;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearToken();
    window.dispatchEvent(new Event("auth:expired"));
    throw new Error("Session expiree");
  }

  return res;
}
```

### 2. Auth Provider (lib/auth.tsx)

```tsx
"use client";
import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getToken, setToken, clearToken, apiFetch } from "./api";

interface AuthUser {
  id: number;
  email: string;
  name: string;
  is_admin?: boolean;
  advertisers?: { id: number; company_name: string; sector: string }[];
}

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  currentAdvertiserId: number | null;
  loginWithToken: (token: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  switchAdvertiser: (id: number) => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentAdvertiserId, setCurrentAdvertiserId] = useState<number | null>(null);
  const router = useRouter();

  const refresh = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const res = await apiFetch("/auth/me");
      if (!res.ok) throw new Error("Auth failed");
      const data = await res.json();
      setUser(data);

      // Restaurer ou selectionner le premier advertiser
      const stored = localStorage.getItem("current_advertiser_id");
      const advIds = (data.advertisers || []).map((a: any) => a.id);
      if (stored && advIds.includes(Number(stored))) {
        setCurrentAdvertiserId(Number(stored));
      } else if (advIds.length > 0) {
        setCurrentAdvertiserId(advIds[0]);
        localStorage.setItem("current_advertiser_id", String(advIds[0]));
      }
    } catch {
      clearToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const loginWithToken = useCallback(async (token: string) => {
    setToken(token);
    await refresh();
  }, [refresh]);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    setCurrentAdvertiserId(null);
    const msAuthUrl = process.env.NEXT_PUBLIC_MS_REMOTE_AUTH_URL;
    if (msAuthUrl) {
      window.location.href = `${msAuthUrl}?action=sign-out&to=${window.location.origin}/login`;
    } else {
      router.push("/login");
    }
  }, [router]);

  const switchAdvertiser = useCallback((id: number) => {
    setCurrentAdvertiserId(id);
    localStorage.setItem("current_advertiser_id", String(id));
    // Invalider le cache SWR pour recharger les donnees
    window.dispatchEvent(new Event("advertiser:changed"));
  }, []);

  useEffect(() => {
    refresh();
    const handleExpired = () => { clearToken(); setUser(null); router.push("/login"); };
    window.addEventListener("auth:expired", handleExpired);
    return () => window.removeEventListener("auth:expired", handleExpired);
  }, [refresh, router]);

  return (
    <AuthContext.Provider value={{ user, loading, currentAdvertiserId, loginWithToken, logout, refresh, switchAdvertiser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
};
```

### 3. Page Login (app/login/page.tsx)

```tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { exchangeMobsuccessAuth } from "@/lib/api";

export default function LoginPage() {
  const { user, loginWithToken } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Redirect si deja connecte
  useEffect(() => {
    if (user) router.push("/");
  }, [user, router]);

  // Callback SSO: /login?userId=...&authId=...
  useEffect(() => {
    const userId = params.get("userId");
    const authId = params.get("authId");
    if (userId && authId) {
      handleSSOCallback(userId, authId);
    }
  }, [params]);

  async function handleSSOCallback(userId: string, authId: string) {
    setLoading(true);
    try {
      const token = await exchangeMobsuccessAuth(userId, authId);
      await loginWithToken(token);
      // Clean URL et redirect
      router.replace("/");
    } catch (err: any) {
      setError(err.message || "Erreur d'authentification");
    } finally {
      setLoading(false);
    }
  }

  const msAuthUrl = process.env.NEXT_PUBLIC_MS_REMOTE_AUTH_URL;
  const returnUrl = typeof window !== "undefined"
    ? `${window.location.origin}/login`
    : "/login";

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="max-w-sm w-full space-y-6">
        <h1 className="text-2xl font-bold text-center">Connexion</h1>

        {error && <p className="text-red-500 text-sm">{error}</p>}

        {loading ? (
          <p className="text-center">Connexion en cours...</p>
        ) : (
          <>
            {/* Bouton SSO Mobsuccess */}
            {msAuthUrl && (
              <a
                href={`${msAuthUrl}?to=${encodeURIComponent(returnUrl)}`}
                className="w-full block text-center bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700"
              >
                Se connecter avec Mobsuccess
              </a>
            )}

            {/* Separateur */}
            <div className="flex items-center gap-4">
              <hr className="flex-1" />
              <span className="text-sm text-gray-400">ou</span>
              <hr className="flex-1" />
            </div>

            {/* Formulaire email/password (fallback) */}
            <form onSubmit={handleEmailLogin} className="space-y-4">
              {/* ... inputs email + password + submit */}
            </form>
          </>
        )}
      </div>
    </div>
  );
}
```

## Multi-Enseigne (Advertiser Switching)

Le systeme supporte plusieurs enseignes par utilisateur :

1. **Table de liaison** : `UserAdvertiser(user_id, advertiser_id, role)`
2. **Header HTTP** : `X-Advertiser-Id` envoye avec chaque requete API
3. **Frontend** : `switchAdvertiser(id)` dans le contexte Auth
4. **Backend** : `parse_advertiser_header()` + `get_user_competitor_ids(db, user, adv_id)` pour filtrer les donnees

### Composant Switcher

```tsx
function AdvertiserSwitcher() {
  const { user, currentAdvertiserId, switchAdvertiser } = useAuth();
  if (!user?.advertisers?.length) return null;

  return (
    <select
      value={currentAdvertiserId || ""}
      onChange={(e) => switchAdvertiser(Number(e.target.value))}
    >
      {user.advertisers.map((adv) => (
        <option key={adv.id} value={adv.id}>
          {adv.company_name}
        </option>
      ))}
    </select>
  );
}
```

## Decisions architecturales

| Decision | Justification |
|----------|---------------|
| Decode JWT Cognito sans verification de signature | Token de confiance via getauthid-auth, approche vibely-stack |
| ID deterministe `abs(hash(sub)) % 2**31` | Permet de retrouver le user par son sub Cognito |
| Upsert par email d'abord | La plupart des users ont deja un compte local |
| Token dans localStorage | Simple, accessible depuis toutes les pages |
| `X-Advertiser-Id` header | Selection multi-enseigne explicite, sans query params |
| Invalidation cache SWR au switch | Toutes les donnees rechargees pour le nouvel annonceur |

## Checklist d'integration

- [ ] Ajouter `MS_AUTH_ENABLED=true` dans les variables d'env backend
- [ ] Ajouter `JWT_SECRET` dans SSM Parameter Store (prod)
- [ ] Ajouter les 3 variables `NEXT_PUBLIC_MS_*` dans le frontend
- [ ] Creer les tables `users`, `advertisers`, `user_advertisers`
- [ ] Implementer `core/auth.py` avec la chaine de fallback JWT local -> Cognito
- [ ] Ajouter `AuthProvider` dans le layout root du frontend
- [ ] Configurer le bouton SSO sur la page login
- [ ] Tester le flow complet: login -> callback -> token -> /me -> donnees filtrees

## Depannage

| Probleme | Solution |
|----------|----------|
| "Token expire" apres login | Verifier que `exp` dans le JWT Cognito est dans le futur |
| User cree mais pas d'advertisers | Ajouter des lignes dans `user_advertisers` (admin ou onboarding) |
| 401 sur toutes les requetes | Verifier `MS_AUTH_ENABLED=true` dans le backend |
| SSO redirect ne revient pas | Verifier `NEXT_PUBLIC_MS_REMOTE_AUTH_URL` et le `returnUrl` |
| Donnees vides apres switch advertiser | Verifier que l'event `advertiser:changed` invalide le cache SWR |

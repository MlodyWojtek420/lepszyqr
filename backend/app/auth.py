import hmac
import time
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel

from . import config

COOKIE_NAME = "session"
router = APIRouter(prefix="/api/auth")

_fails: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _check_rate(ip: str) -> None:
    now = time.time()
    recent = [t for t in _fails.get(ip, []) if now - t < 300]
    _fails[ip] = recent
    if len(recent) >= 8:
        raise HTTPException(429, "Zbyt wiele nieudanych prób logowania. Spróbuj za kilka minut.")


def require_admin(session: str | None = Cookie(default=None)) -> str:
    if not session:
        raise HTTPException(401, "Wymagane logowanie")
    try:
        payload = jwt.decode(session, config.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Sesja wygasła – zaloguj się ponownie")
    return payload["sub"]


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    ip = _client_ip(request)
    _check_rate(ip)
    ok_user = hmac.compare_digest(body.username.encode(), config.ADMIN_USER.encode())
    ok_pass = hmac.compare_digest(body.password.encode(), config.ADMIN_PASSWORD.encode())
    if not (ok_user and ok_pass):
        _fails.setdefault(ip, []).append(time.time())
        raise HTTPException(401, "Nieprawidłowa nazwa użytkownika lub hasło")
    exp = datetime.now(timezone.utc) + timedelta(hours=config.SESSION_HOURS)
    token = jwt.encode({"sub": config.ADMIN_USER, "exp": exp}, config.SECRET_KEY, algorithm="HS256")
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="lax",
        secure=config.COOKIE_SECURE, max_age=config.SESSION_HOURS * 3600, path="/",
    )
    return {"user": config.ADMIN_USER}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(session: str | None = Cookie(default=None)):
    return {"user": require_admin(session)}

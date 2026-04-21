from secrets import compare_digest, token_urlsafe
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import get_db
from app.models import User

router = APIRouter()

SESSION_COOKIE_NAME = "ipc_eval_session"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
_sessions: dict[str, str] = {}


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthUserResponse(BaseModel):
    username: str


def require_auth(request: Request) -> str:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    username = _sessions.get(session_token or "")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已失效",
        )
    return username


@router.post("/login", response_model=AuthUserResponse, summary="用户登录")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    settings = get_settings()
    is_admin_login = (
        compare_digest(payload.username, settings.admin_username)
        and compare_digest(payload.password, settings.admin_password)
    )

    if not is_admin_login:
        user = db.query(User).filter(User.username == payload.username, User.deleted_at.is_(None)).first()
        input_password_hash = hashlib.sha256(payload.password.encode("utf-8")).hexdigest()
        if not user or user.status != "active" or not compare_digest(user.password_hash, input_password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

    session_token = token_urlsafe(32)
    _sessions[session_token] = payload.username
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return AuthUserResponse(username=payload.username)


@router.post("/logout", summary="退出登录", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response):
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if session_token:
        _sessions.pop(session_token, None)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=AuthUserResponse, summary="获取当前登录用户")
def get_me(username: str = Depends(require_auth)):
    return AuthUserResponse(username=username)

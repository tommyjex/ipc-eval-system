from datetime import datetime
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth import require_auth
from app.core.config import get_settings
from app.core.database import get_db
from app.models import User
from app.schemas.user import (
    UserCreate,
    UserListResponse,
    UserResetPasswordRequest,
    UserResponse,
    UserUpdate,
)

router = APIRouter()


def require_admin(username: str = Depends(require_auth)) -> str:
    settings = get_settings()
    if username != settings.admin_username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可执行该操作",
        )
    return username


def _hash_password(password: str) -> str:
    # 骨架实现：后续应替换为 bcrypt / passlib
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


@router.get("/users", response_model=UserListResponse, summary="获取用户列表")
def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str | None = Query(None, description="用户名/昵称关键词"),
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User).filter(User.deleted_at.is_(None))
    if keyword:
        like_keyword = f"%{keyword}%"
        query = query.filter((User.username.like(like_keyword)) | (User.nickname.like(like_keyword)))

    total = query.count()
    items = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return UserListResponse(items=items, total=total)


@router.get("/users/{user_id}", response_model=UserResponse, summary="获取用户详情")
def get_user(
    user_id: int,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user


@router.post("/users", response_model=UserResponse, summary="管理员创建用户")
def create_user(
    payload: UserCreate,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    existing_user = db.query(User).filter(User.username == payload.username, User.deleted_at.is_(None)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )

    user = User(
        username=payload.username,
        password_hash=_hash_password(payload.password),
        nickname=payload.nickname,
        role=payload.role.value,
        status=payload.status.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserResponse, summary="管理员更新用户")
def update_user(
    user_id: int,
    payload: UserUpdate,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if payload.nickname is not None:
        user.nickname = payload.nickname
    if payload.role is not None:
        user.role = payload.role.value
    if payload.status is not None:
        user.status = payload.status.value

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="管理员删除用户")
def delete_user(
    user_id: int,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    user.deleted_at = datetime.now()
    db.commit()


@router.post("/users/{user_id}/reset-password", response_model=UserResponse, summary="管理员重置用户密码")
def reset_user_password(
    user_id: int,
    payload: UserResetPasswordRequest,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    user.password_hash = _hash_password(payload.password)
    db.commit()
    db.refresh(user)
    return user

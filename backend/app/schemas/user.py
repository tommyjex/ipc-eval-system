from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    admin = "admin"
    user = "user"


class UserStatus(str, Enum):
    active = "active"
    disabled = "disabled"


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="登录用户名")
    nickname: Optional[str] = Field(None, max_length=100, description="用户昵称")
    role: UserRole = Field(default=UserRole.user, description="用户角色")
    status: UserStatus = Field(default=UserStatus.active, description="账号状态")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100, description="登录密码")


class UserUpdate(BaseModel):
    nickname: Optional[str] = Field(None, max_length=100, description="用户昵称")
    role: Optional[UserRole] = Field(None, description="用户角色")
    status: Optional[UserStatus] = Field(None, description="账号状态")


class UserResetPasswordRequest(BaseModel):
    password: str = Field(..., min_length=8, max_length=100, description="新密码")


class UserResponse(BaseModel):
    id: int
    username: str
    nickname: Optional[str] = None
    role: UserRole
    status: UserStatus
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int

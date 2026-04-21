from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Index
from sqlalchemy.sql import func

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, unique=True, comment="登录用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    nickname = Column(String(100), comment="用户昵称")
    role = Column(
        Enum("admin", "user", name="user_role"),
        nullable=False,
        default="user",
        server_default="user",
        comment="用户角色",
    )
    status = Column(
        Enum("active", "disabled", name="user_status"),
        nullable=False,
        default="active",
        server_default="active",
        comment="账号状态",
    )
    last_login_at = Column(DateTime(timezone=True), comment="最近登录时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")
    deleted_at = Column(DateTime(timezone=True), comment="逻辑删除时间")

    __table_args__ = (
        Index("idx_users_username", "username", unique=True),
        Index("idx_users_role", "role"),
        Index("idx_users_status", "status"),
        Index("idx_users_created_at", "created_at"),
        Index("idx_users_deleted_at", "deleted_at"),
    )

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"

import hashlib

from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.users import require_admin, router
from app.core.database import get_db
from app.models.base import Base


SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def build_test_client(admin_override):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin] = admin_override
    return TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE IF EXISTS users")
        connection.exec_driver_sql(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(64) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                nickname VARCHAR(100),
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                last_login_at DATETIME NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NULL,
                deleted_at DATETIME NULL
            )
            """
        )


def test_admin_can_create_user_successfully():
    client = build_test_client(lambda: "admin")

    response = client.post(
        "/api/users",
        json={
            "username": "normal_user",
            "password": "Password123",
            "nickname": "普通用户",
            "role": "user",
            "status": "active",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "normal_user"
    assert data["nickname"] == "普通用户"
    assert data["role"] == "user"
    assert data["status"] == "active"
    assert "password" not in data

    db = TestingSessionLocal()
    try:
        row = db.execute(
            text("SELECT username, password_hash FROM users WHERE username = :username"),
            {"username": "normal_user"},
        ).fetchone()
        assert row is not None
        assert row[0] == "normal_user"
        assert row[1] == hashlib.sha256("Password123".encode("utf-8")).hexdigest()
    finally:
        db.close()


def test_admin_cannot_create_duplicate_username():
    client = build_test_client(lambda: "admin")

    payload = {
        "username": "duplicate_user",
        "password": "Password123",
        "nickname": "重复用户",
        "role": "user",
        "status": "active",
    }
    first_response = client.post("/api/users", json=payload)
    second_response = client.post("/api/users", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 400
    assert second_response.json()["detail"] == "用户名已存在"


def test_non_admin_cannot_create_user():
    def deny_non_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可执行该操作",
        )

    client = build_test_client(deny_non_admin)

    response = client.post(
        "/api/users",
        json={
            "username": "forbidden_user",
            "password": "Password123",
            "nickname": "无权限用户",
            "role": "user",
            "status": "active",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "仅管理员可执行该操作"


def test_admin_can_update_user_successfully():
    client = build_test_client(lambda: "admin")

    create_response = client.post(
        "/api/users",
        json={
            "username": "update_user",
            "password": "Password123",
            "nickname": "原始昵称",
            "role": "user",
            "status": "active",
        },
    )
    user_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/users/{user_id}",
        json={
            "nickname": "更新后的昵称",
            "role": "admin",
            "status": "disabled",
        },
    )

    assert update_response.status_code == 200
    data = update_response.json()
    assert data["id"] == user_id
    assert data["nickname"] == "更新后的昵称"
    assert data["role"] == "admin"
    assert data["status"] == "disabled"


def test_update_user_returns_404_when_user_not_found():
    client = build_test_client(lambda: "admin")

    response = client.put(
        "/api/users/99999",
        json={
            "nickname": "不存在的用户",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "用户不存在"


def test_non_admin_cannot_update_user():
    admin_client = build_test_client(lambda: "admin")
    create_response = admin_client.post(
        "/api/users",
        json={
            "username": "need_protection",
            "password": "Password123",
            "nickname": "待保护用户",
            "role": "user",
            "status": "active",
        },
    )
    user_id = create_response.json()["id"]

    def deny_non_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可执行该操作",
        )

    client = build_test_client(deny_non_admin)
    response = client.put(
        f"/api/users/{user_id}",
        json={
            "nickname": "无权限更新",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "仅管理员可执行该操作"


def test_admin_can_delete_user_successfully():
    client = build_test_client(lambda: "admin")

    create_response = client.post(
        "/api/users",
        json={
            "username": "delete_user",
            "password": "Password123",
            "nickname": "待删除用户",
            "role": "user",
            "status": "active",
        },
    )
    user_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/users/{user_id}")
    assert delete_response.status_code == 204
    assert delete_response.content == b""

    detail_response = client.get(f"/api/users/{user_id}")
    assert detail_response.status_code == 404
    assert detail_response.json()["detail"] == "用户不存在"


def test_delete_user_returns_404_when_user_not_found():
    client = build_test_client(lambda: "admin")

    response = client.delete("/api/users/99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "用户不存在"


def test_non_admin_cannot_delete_user():
    admin_client = build_test_client(lambda: "admin")
    create_response = admin_client.post(
        "/api/users",
        json={
            "username": "delete_protected_user",
            "password": "Password123",
            "nickname": "待保护删除用户",
            "role": "user",
            "status": "active",
        },
    )
    user_id = create_response.json()["id"]

    def deny_non_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可执行该操作",
        )

    client = build_test_client(deny_non_admin)
    response = client.delete(f"/api/users/{user_id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "仅管理员可执行该操作"


def test_admin_can_reset_user_password():
    client = build_test_client(lambda: "admin")

    create_response = client.post(
        "/api/users",
        json={
            "username": "reset_user",
            "password": "Password123",
            "nickname": "待重置密码用户",
            "role": "user",
            "status": "active",
        },
    )
    user_id = create_response.json()["id"]

    response = client.post(
        f"/api/users/{user_id}/reset-password",
        json={"password": "NewPassword456"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["username"] == "reset_user"

    db = TestingSessionLocal()
    try:
        row = db.execute(
            text("SELECT password_hash FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        ).fetchone()
        assert row is not None
        assert row[0] == hashlib.sha256("NewPassword456".encode("utf-8")).hexdigest()
    finally:
        db.close()


def test_reset_password_returns_404_when_user_not_found():
    client = build_test_client(lambda: "admin")

    response = client.post(
        "/api/users/99999/reset-password",
        json={"password": "NewPassword456"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "用户不存在"


def test_non_admin_cannot_reset_user_password():
    admin_client = build_test_client(lambda: "admin")
    create_response = admin_client.post(
        "/api/users",
        json={
            "username": "reset_protected_user",
            "password": "Password123",
            "nickname": "待保护重置密码用户",
            "role": "user",
            "status": "active",
        },
    )
    user_id = create_response.json()["id"]

    def deny_non_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可执行该操作",
        )

    client = build_test_client(deny_non_admin)
    response = client.post(
        f"/api/users/{user_id}/reset-password",
        json={"password": "NewPassword456"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "仅管理员可执行该操作"

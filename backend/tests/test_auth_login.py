import hashlib

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.api.auth import router
from app.core.config import get_settings
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


def build_test_client():
    app = FastAPI()
    app.include_router(router, prefix="/api/auth")
    app.dependency_overrides[get_db] = override_get_db
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


def test_admin_can_login_with_env_credentials(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password")
    get_settings.cache_clear()
    client = build_test_client()
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-admin-password"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "admin"
    get_settings.cache_clear()


def test_normal_user_can_login_with_database_credentials():
    db = TestingSessionLocal()
    try:
        db.execute(
            text(
                """
            INSERT INTO users (username, password_hash, role, status)
            VALUES (:username, :password_hash, :role, :status)
            """
            ),
            {
                "username": "xujianhua",
                "password_hash": hashlib.sha256("Password123".encode("utf-8")).hexdigest(),
                "role": "user",
                "status": "active",
            },
        )
        db.commit()
    finally:
        db.close()

    client = build_test_client()
    response = client.post(
        "/api/auth/login",
        json={"username": "xujianhua", "password": "Password123"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "xujianhua"


def test_disabled_user_login_should_fail():
    db = TestingSessionLocal()
    try:
        db.execute(
            text(
                """
            INSERT INTO users (username, password_hash, role, status)
            VALUES (:username, :password_hash, :role, :status)
            """
            ),
            {
                "username": "disabled_user",
                "password_hash": hashlib.sha256("Password123".encode("utf-8")).hexdigest(),
                "role": "user",
                "status": "disabled",
            },
        )
        db.commit()
    finally:
        db.close()

    client = build_test_client()
    response = client.post(
        "/api/auth/login",
        json={"username": "disabled_user", "password": "Password123"},
    )
    assert response.status_code == 401

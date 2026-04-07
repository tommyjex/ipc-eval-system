import socket
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.core.config import get_settings
from app.models.base import Base

settings = get_settings()

# 解析域名为IP地址
db_host = settings.db_host
try:
    ip_address = socket.gethostbyname(db_host)
    connect_host = ip_address
except socket.gaierror:
    connect_host = db_host

# 对密码进行URL编码，处理特殊字符
encoded_password = quote_plus(settings.db_password)

# 构建使用IP地址的数据库URL
database_url = f"mysql+pymysql://{settings.db_user}:{encoded_password}@{connect_host}:{settings.db_port}/{settings.db_name}"

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.debug,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)

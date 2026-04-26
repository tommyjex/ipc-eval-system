import socket
from urllib.parse import quote_plus
from sqlalchemy import create_engine, inspect, text
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

# 构建使用IP地址的数据库URL，并显式使用 utf8mb4 以支持 emoji 等 4 字节字符
database_url = f"mysql+pymysql://{settings.db_user}:{encoded_password}@{connect_host}:{settings.db_port}/{settings.db_name}?charset=utf8mb4"

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sync_task_result_metric_columns():
    inspector = inspect(engine)
    if "task_results" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("task_results")}
    alter_statements: list[str] = []

    if "precision" not in existing_columns:
        alter_statements.append("ALTER TABLE task_results ADD COLUMN `precision` FLOAT NULL COMMENT '精确率'")
    if "tp_count" not in existing_columns:
        alter_statements.append("ALTER TABLE task_results ADD COLUMN tp_count BIGINT NULL COMMENT '命中数量'")
    if "fp_count" not in existing_columns:
        alter_statements.append("ALTER TABLE task_results ADD COLUMN fp_count BIGINT NULL COMMENT '误报数量'")
    if "fn_count" not in existing_columns:
        alter_statements.append("ALTER TABLE task_results ADD COLUMN fn_count BIGINT NULL COMMENT '漏检数量'")
    if "ground_truth_unit_count" not in existing_columns:
        alter_statements.append("ALTER TABLE task_results ADD COLUMN ground_truth_unit_count BIGINT NULL COMMENT '标注单元数'")
    if "predicted_unit_count" not in existing_columns:
        alter_statements.append("ALTER TABLE task_results ADD COLUMN predicted_unit_count BIGINT NULL COMMENT '预测单元数'")
    if "is_scorable" not in existing_columns:
        alter_statements.append("ALTER TABLE task_results ADD COLUMN is_scorable BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否可参与评分'")
    if "is_empty_sample" not in existing_columns:
        alter_statements.append("ALTER TABLE task_results ADD COLUMN is_empty_sample BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否为空样本'")
    if "empty_sample_passed" not in existing_columns:
        alter_statements.append("ALTER TABLE task_results ADD COLUMN empty_sample_passed BOOLEAN NOT NULL DEFAULT FALSE COMMENT '空样本是否判断正确'")
    if "metric_version" not in existing_columns:
        alter_statements.append("ALTER TABLE task_results ADD COLUMN metric_version VARCHAR(32) NULL COMMENT '评分口径版本'")

    with engine.begin() as connection:
        for statement in alter_statements:
            connection.execute(text(statement))
        if "accuracy" in existing_columns:
            connection.execute(
                text(
                    "UPDATE task_results "
                    "SET `precision` = accuracy "
                    "WHERE `precision` IS NULL AND accuracy IS NOT NULL"
                )
            )


def _sync_evaluation_task_columns():
    inspector = inspect(engine)
    if "evaluation_tasks" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("evaluation_tasks")}
    alter_statements: list[str] = []

    if "username" not in existing_columns:
        alter_statements.append("ALTER TABLE evaluation_tasks ADD COLUMN username VARCHAR(64) NULL COMMENT '创建用户名'")

    with engine.begin() as connection:
        for statement in alter_statements:
            connection.execute(text(statement))


def init_db():
    Base.metadata.create_all(bind=engine)
    _sync_evaluation_task_columns()
    _sync_task_result_metric_columns()

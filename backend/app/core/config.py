from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "摄像头场景大模型评测平台"
    app_version: str = "0.1.0"
    debug: bool = True
    port: int = 3000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"]
    admin_username: str = "admin"
    admin_password: str

    tos_access_key: str 
    tos_secret_key: str 
    tos_endpoint: str = "tos-cn-beijing.volces.com"
    tos_public_endpoint: str = "tos-cn-beijing.volces.com"
    tos_region: str = "cn-beijing"
    tos_bucket: str = "xujianhua-utils"

    ark_api_key: str 
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_model: str = "ep-20260215001006-86n7g"
    ark_timeout: int = 20
    ark_max_retries: int = 2

    # 阿里百炼 DashScope
    dashscope_api_key: str
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    dashscope_debug_response: bool = False
    task_inference_batch_size: int = 50
    task_scoring_batch_size: int = 200
    task_single_timeout_seconds: int = 120

    db_host: str = "mysqlf4d4d1585fb1.rds.ivolces.com"
    db_port: int = 3306
    db_user: str = "xujianhua"
    db_password: str
    db_name: str = "ipc-eval"

    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()

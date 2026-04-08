from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api import health, datasets, evaluation_data, annotations, tasks

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="摄像头场景大模型评测平台API服务",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["健康检查"])
app.include_router(datasets.router, prefix="/api/datasets", tags=["评测集管理"])
app.include_router(evaluation_data.router, prefix="/api/datasets", tags=["评测数据管理"])
app.include_router(annotations.router, prefix="/api", tags=["数据标注"])
app.include_router(tasks.router, prefix="/api", tags=["评测任务"])


@app.get("/")
async def root():
    return {"message": "欢迎使用摄像头场景大模型评测平台API", "docs": "/docs"}

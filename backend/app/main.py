from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.database import init_db
from app.api import auth, health, datasets, evaluation_data, annotations, tasks, scoring_templates, prompt_templates

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

protected_dependencies = [Depends(auth.require_auth)]

app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(health.router, prefix="/api", tags=["健康检查"])
app.include_router(datasets.router, prefix="/api/datasets", tags=["评测集管理"], dependencies=protected_dependencies)
app.include_router(evaluation_data.router, prefix="/api/datasets", tags=["评测数据管理"], dependencies=protected_dependencies)
app.include_router(annotations.router, prefix="/api", tags=["数据标注"], dependencies=protected_dependencies)
app.include_router(tasks.router, prefix="/api", tags=["评测任务"], dependencies=protected_dependencies)
app.include_router(scoring_templates.router, prefix="/api", tags=["评分标准模板"], dependencies=protected_dependencies)
app.include_router(prompt_templates.router, prefix="/api", tags=["任务 Prompt 模板"], dependencies=protected_dependencies)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
async def root():
    return {"message": "欢迎使用摄像头场景大模型评测平台API", "docs": "/docs"}

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.dataset import DatasetScene


class TaskPromptTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="模板名称")
    scene: DatasetScene = Field(..., description="业务场景")
    description: Optional[str] = Field(None, max_length=500, description="模板描述")
    content: str = Field(..., min_length=1, description="任务 Prompt 模板内容")


class TaskPromptTemplateCreate(TaskPromptTemplateBase):
    pass


class TaskPromptTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="模板名称")
    scene: Optional[DatasetScene] = Field(None, description="业务场景")
    description: Optional[str] = Field(None, max_length=500, description="模板描述")
    content: Optional[str] = Field(None, min_length=1, description="任务 Prompt 模板内容")


class TaskPromptTemplateResponse(TaskPromptTemplateBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaskPromptTemplateListResponse(BaseModel):
    items: list[TaskPromptTemplateResponse]
    total: int

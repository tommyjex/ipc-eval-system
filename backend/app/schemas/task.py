from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ModelProvider(str, Enum):
    volcengine = "volcengine"
    aliyun = "aliyun"
    gemini = "gemini"
    openai = "openai"
    aws = "aws"


class EvaluationTaskBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="任务名称")
    target_model: str = Field(..., max_length=100, description="目标模型")
    model_provider: Optional[ModelProvider] = Field(None, description="模型供应商")
    scoring_criteria: Optional[str] = Field(None, description="评分标准")


class EvaluationTaskCreate(EvaluationTaskBase):
    dataset_id: int = Field(..., description="评测集ID")


class EvaluationTaskUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="任务名称")
    target_model: Optional[str] = Field(None, max_length=100, description="目标模型")
    model_provider: Optional[ModelProvider] = Field(None, description="模型供应商")
    scoring_criteria: Optional[str] = Field(None, description="评分标准")
    status: Optional[TaskStatus] = Field(None, description="任务状态")


class EvaluationTaskResponse(EvaluationTaskBase):
    id: int
    dataset_id: int
    status: TaskStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EvaluationTaskListResponse(BaseModel):
    items: list[EvaluationTaskResponse]
    total: int


class TaskResultBase(BaseModel):
    model_output: Optional[str] = Field(None, description="模型输出")
    score: Optional[int] = Field(None, description="评分")
    score_reason: Optional[str] = Field(None, description="评分原因")


class TaskResultResponse(TaskResultBase):
    id: int
    task_id: int
    data_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TaskResultListResponse(BaseModel):
    items: list[TaskResultResponse]
    total: int


class TaskResultDetailResponse(TaskResultResponse):
    file_name: str = Field(..., description="文件名")
    file_type: str = Field(..., description="文件类型")
    download_url: Optional[str] = Field(None, description="下载链接")
    ground_truth: Optional[str] = Field(None, description="标注结果")

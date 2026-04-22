from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class TaskResultStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class TaskScoringStatus(str, Enum):
    not_scored = "not_scored"
    scoring = "scoring"
    scored = "scored"
    score_failed = "score_failed"


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
    prompt: Optional[str] = Field(None, description="任务级提示词")
    fps: float = Field(0.3, ge=0.01, le=30, description="视频理解帧率")


class EvaluationTaskCreate(EvaluationTaskBase):
    dataset_id: int = Field(..., description="评测集ID")


class EvaluationTaskUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="任务名称")
    target_model: Optional[str] = Field(None, max_length=100, description="目标模型")
    model_provider: Optional[ModelProvider] = Field(None, description="模型供应商")
    scoring_criteria: Optional[str] = Field(None, description="评分标准")
    prompt: Optional[str] = Field(None, description="任务级提示词")
    fps: Optional[float] = Field(None, ge=0.01, le=30, description="视频理解帧率")
    status: Optional[TaskStatus] = Field(None, description="任务状态")


class EvaluationTaskRunRequest(BaseModel):
    data_ids: Optional[list[int]] = Field(None, description="指定重跑的数据ID列表")


class EvaluationTaskScoreRequest(BaseModel):
    result_ids: Optional[list[int]] = Field(None, description="指定评分的结果ID列表")


class EvaluationTaskResponse(EvaluationTaskBase):
    id: int
    dataset_id: int
    status: TaskStatus
    avg_recall: Optional[float] = None
    avg_accuracy: Optional[float] = None
    avg_input_tokens: Optional[float] = None
    avg_output_tokens: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EvaluationTaskListResponse(BaseModel):
    items: list[EvaluationTaskResponse]
    total: int


class TaskResultBase(BaseModel):
    status: TaskResultStatus = Field(..., description="执行状态")
    model_output: Optional[str] = Field(None, description="模型输出")
    input_tokens: Optional[int] = Field(None, description="输入 tokens")
    output_tokens: Optional[int] = Field(None, description="输出 tokens")
    score: Optional[int] = Field(None, description="评分")
    recall: Optional[float] = Field(None, description="召回率")
    accuracy: Optional[float] = Field(None, description="准确率")
    score_reason: Optional[str] = Field(None, description="评分原因")
    scoring_status: TaskScoringStatus = Field(..., description="评分状态")
    scoring_error_message: Optional[str] = Field(None, description="评分失败原因")
    scoring_model: Optional[str] = Field(None, description="评分模型")
    error_message: Optional[str] = Field(None, description="失败原因")


class TaskResultResponse(TaskResultBase):
    id: int
    task_id: int
    data_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    scoring_started_at: Optional[datetime] = None
    scoring_completed_at: Optional[datetime] = None

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


class TaskResultDetailListResponse(BaseModel):
    items: list[TaskResultDetailResponse]
    total: int
    avg_recall: Optional[float] = None
    avg_accuracy: Optional[float] = None
    avg_input_tokens: Optional[float] = None
    avg_output_tokens: Optional[float] = None


class TaskResultSelectionResponse(BaseModel):
    total: int
    result_ids: list[int]
    data_ids: list[int]
